"""Gemini AI orchestration service with controlled function calling and strict scoring boundaries."""

import asyncio
import logging
import time
import uuid
from typing import Any

from google import genai
from google.genai import types

from repovet_mcp.config.settings import Settings, get_settings
from repovet_mcp.models.audit import AuditDecision, AuditReport, HardGateResult, Scorecard
from repovet_mcp.orchestration.github_mcp_client import GitHubMCPClient
from repovet_mcp.orchestration.mcp_client import BaseMCPClient, MCPClientError
from repovet_mcp.orchestration.models import (
    OrchestrationRequest,
    OrchestrationResult,
    ToolCallRecord,
)
from repovet_mcp.orchestration.schema_normalizer import normalize_schema_for_gemini
from repovet_mcp.orchestration.shinobi_mcp_client import ShinobiMCPClient
from repovet_mcp.services.github_client import parse_repository_target
from repovet_mcp.services.security import (
    redact_secrets,
    register_secret_for_redaction,
    validate_audit_id,
)

logger = logging.getLogger("repovet_mcp.orchestration.gemini")

ORCHESTRATOR_SYSTEM_INSTRUCTION = """You are Shinobi Orchestrator, an AI assistant specialized in autonomous open-source repository vetting and GSoC due diligence.

You have access to tools from two Model Context Protocol (MCP) servers:
1. Shinobi MCP Server: The authoritative deterministic vetting engine for repository auditing, hard-gate checks, responsiveness analytics, 10-criterion scoring, evidence validation, and PDF generation.
2. GitHub MCP Server: Read-only exploratory tools for discovering repository context, searching issues, commits, and releases.

MANDATORY RULES:
- Never fabricate metrics, commit counts, response times, or audit scores.
- Shinobi is the SOLE deterministic authority for repository eligibility, scorecard calculation (0-20), and final verdicts (APPROVE, CONDITIONAL, REJECT, NEEDS MANUAL REVIEW).
- You MUST NEVER calculate, alter, or override Shinobi scores or decisions.
- When vetting a repository, initialize the audit with 'analyze_repository', evaluate gates with 'check_hard_gates', evaluate responsiveness and accessibility, and calculate the scorecard using 'calculate_scorecard'.
- Clearly distinguish GitHub MCP exploratory observations from Shinobi-verified grounded evidence.
- If data is missing or inaccessible, report it transparently as UNKNOWN rather than guessing.
"""


def _extract_tool_schema(tool: Any) -> dict[str, Any]:
    """Safely extract input schema dict from an MCP Tool object."""
    schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None)
    if isinstance(schema, dict):
        return schema
    return {"type": "object"}


class GeminiOrchestrator:
    """Orchestrates autonomous repository vetting using Gemini function calling and MCP clients."""

    def __init__(
        self,
        settings: Settings | None = None,
        shinobi_client: ShinobiMCPClient | None = None,
        github_client: GitHubMCPClient | None = None,
        genai_client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.shinobi_client = shinobi_client or ShinobiMCPClient(self.settings)
        self.github_client = github_client or GitHubMCPClient(self.settings)

        # Register configured secrets dynamically for automatic scrubbing
        if self.settings.gemini_api_key:
            register_secret_for_redaction(self.settings.gemini_api_key.get_secret_value())
        if self.settings.github_token:
            register_secret_for_redaction(self.settings.github_token.get_secret_value())

        # Allow dependency injection of genai_client for tests without live credentials
        if genai_client is not None:
            self.genai_client = genai_client
        elif self.settings.has_ai_auth and self.settings.gemini_api_key:
            self.genai_client = genai.Client(
                api_key=self.settings.gemini_api_key.get_secret_value()
            )
        else:
            self.genai_client = None

        self._routing_table: dict[str, BaseMCPClient] = {}
        self._tool_declarations: list[types.FunctionDeclaration] = []
        self._is_initialized = False

    async def initialize(self) -> None:
        """Connect to MCP servers, discover available tools, and build normalized Gemini function declarations."""
        if self._is_initialized:
            return

        self._routing_table.clear()
        self._tool_declarations.clear()

        # Connect Shinobi MCP client
        if not self.shinobi_client.is_connected:
            await self.shinobi_client.connect()

        shinobi_tools = await self.shinobi_client.discover_tools()
        for tool in shinobi_tools:
            self._routing_table[tool.name] = self.shinobi_client
            # Normalize schema for OpenAPI 3.0 Gemini compatibility
            raw_schema = _extract_tool_schema(tool)
            clean_schema = normalize_schema_for_gemini(raw_schema)
            self._tool_declarations.append(
                types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Shinobi deterministic tool {tool.name}",
                    parameters=clean_schema,
                )
            )

        # Connect GitHub MCP client if configured
        try:
            if not self.github_client.is_connected:
                await self.github_client.connect()
            github_tools = await self.github_client.discover_tools()
            for tool in github_tools:
                # Do not overwrite Shinobi tools if there is a name collision
                if tool.name not in self._routing_table:
                    self._routing_table[tool.name] = self.github_client
                    raw_schema = _extract_tool_schema(tool)
                    clean_schema = normalize_schema_for_gemini(raw_schema)
                    self._tool_declarations.append(
                        types.FunctionDeclaration(
                            name=tool.name,
                            description=tool.description
                            or f"GitHub MCP read-only tool {tool.name}",
                            parameters=clean_schema,
                        )
                    )
        except Exception as exc:
            logger.warning(
                "GitHub MCP client connection skipped or failed: %s. Continuing with Shinobi tools.",
                redact_secrets(str(exc)),
            )

        self._is_initialized = True
        logger.info(
            "GeminiOrchestrator initialized with %d function declarations across %d routed tools.",
            len(self._tool_declarations),
            len(self._routing_table),
        )

    def get_tool_routing(self) -> dict[str, str]:
        """Return a mapping of tool names to their responsible MCP client identifier."""
        return {
            name: "shinobi" if client == self.shinobi_client else "github"
            for name, client in self._routing_table.items()
        }

    async def orchestrate(self, request: OrchestrationRequest) -> OrchestrationResult:
        """Execute a full orchestration session driven by Gemini function calling with strict audit locking."""
        start_time = time.monotonic()
        tool_records: list[ToolCallRecord] = []
        github_observations: list[dict[str, Any]] = []

        # F-01: Establish trusted session bindings to prevent audit_id hijacking
        session_audit_id: str | None = None
        session_audit_id_locked = False
        session_target_repo: tuple[str, str] | None = None

        if request.audit_id:
            try:
                session_audit_id = validate_audit_id(request.audit_id)
                session_audit_id_locked = True
            except ValueError as exc:
                msg = f"Invalid request audit_id: {exc}"
                logger.error(msg)
                return OrchestrationResult(
                    prompt=request.prompt,
                    final_summary="Orchestration aborted: Invalid audit_id provided.",
                    is_completed=False,
                    error=msg,
                    total_duration_seconds=time.monotonic() - start_time,
                )

        if request.target_repository:
            try:
                session_target_repo = parse_repository_target(request.target_repository)
            except Exception:
                session_target_repo = None

        # Deterministic state tracking (populated strictly from Shinobi tool outputs)
        tracked_audit_id: str | None = session_audit_id
        tracked_scorecard: Scorecard | None = None
        tracked_decision: AuditDecision | None = None
        tracked_hard_gates: list[HardGateResult] = []
        tracked_evidence_count = 0

        # Validate that Gemini client is available
        if not self.genai_client:
            msg = "Gemini client is not initialized. Provide REPOVET_GEMINI_API_KEY in environment or .env."
            logger.error(msg)
            return OrchestrationResult(
                prompt=request.prompt,
                final_summary="Orchestration failed: Gemini API key is missing or unconfigured.",
                is_completed=False,
                error=msg,
                total_duration_seconds=time.monotonic() - start_time,
            )

        # Initialize clients and tools if not already done
        await self.initialize()

        max_steps = request.max_steps or self.settings.max_orchestration_steps
        timeout_seconds = self.settings.orchestration_timeout_seconds

        # Configure Gemini generation with discovered MCP tools
        gen_config = types.GenerateContentConfig(
            system_instruction=ORCHESTRATOR_SYSTEM_INSTRUCTION,
            temperature=0.0,
            tools=[types.Tool(function_declarations=self._tool_declarations)],
        )

        # Seed conversation history
        user_prompt = request.prompt
        if request.target_repository and request.target_repository not in user_prompt:
            user_prompt = f"{request.prompt}\n\nTarget Repository: {request.target_repository}"

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)])
        ]

        iteration = 0
        final_text = ""
        is_completed = True
        error_message: str | None = None

        try:
            async with asyncio.timeout(timeout_seconds):
                while iteration < max_steps:
                    iteration += 1
                    logger.debug("Orchestration iteration %d/%d...", iteration, max_steps)

                    # Invoke Gemini model
                    response = await self.genai_client.aio.models.generate_content(
                        model=self.settings.ai_model,
                        contents=contents,
                        config=gen_config,
                    )

                    # Check for tool call requests
                    function_calls = getattr(response, "function_calls", None)
                    if not function_calls and response.candidates:
                        # Fallback check on candidate parts
                        c_content = response.candidates[0].content
                        if c_content and c_content.parts:
                            function_calls = [
                                p.function_call for p in c_content.parts if p.function_call
                            ]

                    # If no tool calls requested, we reached natural language conclusion
                    if not function_calls:
                        final_text = response.text or ""
                        logger.info("Gemini finished orchestration with final explanation.")
                        break

                    # Append model's response to contents
                    if response.candidates and response.candidates[0].content:
                        contents.append(response.candidates[0].content)

                    # Execute all function calls requested by the model in this turn
                    function_response_parts: list[types.Part] = []
                    for call in function_calls:
                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        call_name = call.name
                        call_args = dict(call.args or {})
                        t_start = time.monotonic()
                        target_name = "unknown"
                        call_failed = False
                        tool_output: Any = None

                        logger.info(
                            "Gemini requested tool '%s' with args %s",
                            call_name,
                            redact_secrets(str(call_args)),
                        )

                        # Enforce tool authorization and routing
                        if call_name not in self._routing_table:
                            call_failed = True
                            tool_output = {
                                "error": f"Tool '{call_name}' is not recognized or not permitted.",
                                "status": "REJECTED_UNAUTHORIZED",
                            }
                            logger.error(
                                "Gemini requested unauthorized tool '%s'. Rejected.", call_name
                            )
                        else:
                            client = self._routing_table[call_name]
                            target_name = "shinobi" if client == self.shinobi_client else "github"

                            # F-01: Audit session locking and anti-hijacking validation
                            if target_name == "shinobi":
                                if call_name == "analyze_repository":
                                    target_arg = call_args.get("target")
                                    if target_arg:
                                        try:
                                            call_owner, call_repo = parse_repository_target(
                                                target_arg
                                            )
                                            if session_target_repo and (
                                                call_owner.lower(),
                                                call_repo.lower(),
                                            ) != (
                                                session_target_repo[0].lower(),
                                                session_target_repo[1].lower(),
                                            ):
                                                call_failed = True
                                                tool_output = {
                                                    "error": (
                                                        f"Security Violation: Audit session is locked to repository "
                                                        f"'{session_target_repo[0]}/{session_target_repo[1]}'. "
                                                        f"Target switch to '{call_owner}/{call_repo}' was rejected."
                                                    ),
                                                    "status": "REJECTED_TARGET_SWITCH",
                                                }
                                            elif not session_target_repo:
                                                session_target_repo = (call_owner, call_repo)
                                        except Exception as exc:
                                            call_failed = True
                                            tool_output = {
                                                "error": f"Invalid repository target '{target_arg}': {exc}",
                                                "status": "INVALID_TARGET",
                                            }

                                    if not call_failed:
                                        if session_audit_id_locked:
                                            call_args["audit_id"] = session_audit_id
                                        elif call_args.get("audit_id"):
                                            try:
                                                session_audit_id = validate_audit_id(
                                                    call_args["audit_id"]
                                                )
                                            except ValueError as exc:
                                                call_failed = True
                                                tool_output = {
                                                    "error": f"Invalid audit_id format: {exc}",
                                                    "status": "INVALID_AUDIT_ID",
                                                }

                                else:
                                    # All downstream Shinobi tools require an active, locked audit session
                                    if not session_audit_id:
                                        call_failed = True
                                        tool_output = {
                                            "error": (
                                                "Security Violation: No active audit session established. "
                                                "'analyze_repository' must be called first."
                                            ),
                                            "status": "REJECTED_NO_ACTIVE_SESSION",
                                        }
                                    else:
                                        supplied_id = call_args.get("audit_id")
                                        if supplied_id and supplied_id != session_audit_id:
                                            # Block prompt injection / foreign audit hijacking attempt
                                            call_failed = True
                                            tool_output = {
                                                "error": (
                                                    f"Security Violation: Audit session is locked to '{session_audit_id}'. "
                                                    f"Attempted access to foreign audit '{supplied_id}' was rejected."
                                                ),
                                                "status": "REJECTED_AUDIT_HIJACKING",
                                            }
                                        else:
                                            # Forcibly bind call to active session audit ID
                                            call_args["audit_id"] = session_audit_id

                            # Only execute tool if session security checks passed
                            if not call_failed:
                                try:
                                    tool_output = await client.call_tool(
                                        name=call_name,
                                        arguments=call_args,
                                        timeout=self.settings.mcp_timeout_seconds,
                                    )

                                    # Update deterministic audit state if Shinobi tool executed successfully
                                    if target_name == "shinobi" and isinstance(tool_output, dict):
                                        if call_name == "analyze_repository":
                                            if "audit_id" in tool_output:
                                                session_audit_id = tool_output["audit_id"]
                                                session_audit_id_locked = True
                                                tracked_audit_id = session_audit_id
                                            if "owner" in tool_output and "repo" in tool_output:
                                                session_target_repo = (
                                                    tool_output["owner"],
                                                    tool_output["repo"],
                                                )

                                        # Capture scorecard and verdict directly from Shinobi engine
                                        if call_name == "calculate_scorecard":
                                            if "total_score" in tool_output:
                                                tracked_scorecard = Scorecard(
                                                    total_score=tool_output.get("total_score", 0),
                                                    max_possible_score=tool_output.get(
                                                        "max_possible_score", 20
                                                    ),
                                                    percentage=tool_output.get("percentage", 0.0),
                                                    criteria_scores=tool_output.get(
                                                        "criteria_scores", []
                                                    ),
                                                )
                                            if "decision" in tool_output:
                                                try:
                                                    tracked_decision = AuditDecision(
                                                        tool_output["decision"]
                                                    )
                                                except ValueError:
                                                    tracked_decision = (
                                                        AuditDecision.NEEDS_MANUAL_REVIEW
                                                    )
                                            if "hard_gates" in tool_output:
                                                tracked_hard_gates = [
                                                    HardGateResult.model_validate(g)
                                                    for g in tool_output.get("hard_gates", [])
                                                ]

                                        if (
                                            call_name == "check_hard_gates"
                                            and "hard_gates" in tool_output
                                        ):
                                            tracked_hard_gates = [
                                                HardGateResult.model_validate(g)
                                                for g in tool_output.get("hard_gates", [])
                                            ]

                                        if call_name == "validate_evidence":
                                            vr = tool_output.get("validation_results", {})
                                            tracked_evidence_count = vr.get(
                                                "total_evidence_items", tracked_evidence_count
                                            )

                                    elif target_name == "github":
                                        # Record GitHub exploratory observation separately from verified audit evidence
                                        github_observations.append(
                                            {
                                                "tool": call_name,
                                                "arguments": call_args,
                                                "observation": tool_output,
                                            }
                                        )

                                except MCPClientError as exc:
                                    call_failed = True
                                    tool_output = {
                                        "error": redact_secrets(str(exc)),
                                        "status": "EXECUTION_FAILED",
                                    }
                                except Exception as exc:
                                    call_failed = True
                                    tool_output = {
                                        "error": redact_secrets(str(exc)),
                                        "status": "UNEXPECTED_ERROR",
                                    }

                        t_duration = time.monotonic() - t_start
                        tool_records.append(
                            ToolCallRecord(
                                call_id=call_id,
                                tool_name=call_name,
                                arguments=call_args,
                                target_client=target_name,
                                result=tool_output,
                                is_error=call_failed,
                                duration_seconds=t_duration,
                                step_index=iteration,
                            )
                        )

                        # Package response part to return to Gemini
                        response_dict = (
                            tool_output
                            if isinstance(tool_output, dict)
                            else {"result": tool_output}
                        )
                        function_response_parts.append(
                            types.Part.from_function_response(
                                name=call_name,
                                response=response_dict,
                            )
                        )

                    # Append tool responses as user turn
                    contents.append(types.Content(role="user", parts=function_response_parts))

                else:
                    # Loop exhausted max_steps without natural language finish
                    is_completed = False
                    error_message = (
                        f"Orchestration reached maximum iteration limit ({max_steps} steps)."
                    )
                    final_text = (
                        "Orchestration halted: Maximum allowable tool-call iterations reached. "
                        "Partial results and verified deterministic data are preserved."
                    )

        except TimeoutError:
            is_completed = False
            error_message = f"Orchestration session timed out after {timeout_seconds}s."
            final_text = (
                "Orchestration aborted due to overall session timeout. "
                "Deterministic Shinobi results generated prior to timeout have been preserved."
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            is_completed = False
            error_message = redact_secrets(str(exc))
            final_text = f"Orchestration encountered an unhandled error: {error_message}"

        # If Shinobi completed an audit, reload the verified report from storage with owner/repo verification
        final_report: AuditReport | None = None
        if tracked_audit_id:
            try:
                from repovet_mcp.services.storage_service import StorageService

                storage = StorageService(self.settings)
                loaded_report = storage.load_audit_report(tracked_audit_id)
                if loaded_report:
                    # Ensure loaded report target matches the active session target repository
                    if session_target_repo and (
                        loaded_report.target.owner.lower() != session_target_repo[0].lower()
                        or loaded_report.target.repo.lower() != session_target_repo[1].lower()
                    ):
                        logger.error(
                            "Security Mismatch: Audit %s belongs to %s/%s, expected %s/%s. Discarding.",
                            tracked_audit_id,
                            loaded_report.target.owner,
                            loaded_report.target.repo,
                            session_target_repo[0],
                            session_target_repo[1],
                        )
                    else:
                        final_report = loaded_report
                        tracked_scorecard = final_report.scorecard
                        tracked_decision = final_report.decision
                        tracked_hard_gates = final_report.hard_gates
                        tracked_evidence_count = len(final_report.evidence)
            except Exception as e:
                logger.debug("Could not reload audit report from storage: %s", e)

        total_elapsed = time.monotonic() - start_time
        return OrchestrationResult(
            prompt=request.prompt,
            final_summary=final_text,
            audit_id=tracked_audit_id,
            audit_report=final_report,
            scorecard=tracked_scorecard,
            decision=tracked_decision,
            hard_gates=tracked_hard_gates,
            tool_calls=tool_records,
            github_mcp_observations=github_observations,
            shinobi_verified_evidence_count=tracked_evidence_count,
            iterations_used=iteration,
            total_duration_seconds=total_elapsed,
            is_completed=is_completed,
            error=error_message,
        )
