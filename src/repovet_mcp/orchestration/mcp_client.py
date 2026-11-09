"""Asynchronous MCP stdio client abstraction for tool discovery and execution."""

import asyncio
import json
import logging
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from repovet_mcp.services.security import (
    build_isolated_subprocess_env,
    redact_secrets,
    register_secret_for_redaction,
)

logger = logging.getLogger("repovet_mcp.orchestration.client")


class MCPClientError(Exception):
    """Base exception for MCP client connection and protocol failures."""


class MCPToolExecutionError(MCPClientError):
    """Raised when an MCP tool fails during execution or returns an error result."""


class BaseMCPClient:
    """Manages an asynchronous stdio session to an external or local MCP server."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
        cwd: Path | str | None = None,
        client_name: str = "base-mcp-client",
    ) -> None:
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.timeout = timeout
        self.cwd = Path(cwd) if cwd else None
        self.client_name = client_name
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._discovered_tools: dict[str, mcp_types.Tool] = {}
        self._is_connected = False

        # Register custom env values for dynamic secret scrubbing
        if self.env:
            for val in self.env.values():
                register_secret_for_redaction(val)

    @property
    def is_connected(self) -> bool:
        """Check whether the client is currently connected and initialized."""
        return self._is_connected and self._session is not None

    async def connect(self) -> None:
        """Start the stdio subprocess transport and complete protocol initialization."""
        if self.is_connected:
            return

        # Prepare isolated environment: preserve safe runtime variables, strip host ambient secrets
        isolated_env = build_isolated_subprocess_env(custom_env=self.env)

        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=isolated_env,
            cwd=str(self.cwd) if self.cwd else None,
        )

        logger.info(
            "Connecting %s to '%s %s' (cwd: %s)...",
            self.client_name,
            self.command,
            " ".join(self.args),
            self.cwd or "inherited",
        )

        stack = AsyncExitStack()
        try:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))

            # Protocol handshake with timeout
            async with asyncio.timeout(self.timeout):
                init_res = await session.initialize()

            self._exit_stack = stack
            self._session = session
            self._is_connected = True

            logger.info(
                "%s connected successfully (protocol v%s, server '%s').",
                self.client_name,
                init_res.protocol_version,
                init_res.server_info.name if init_res.server_info else "unknown",
            )

            # Discover available tools upon connection
            await self.discover_tools()

        except TimeoutError:
            await stack.aclose()
            msg = f"{self.client_name} connection timed out after {self.timeout}s"
            logger.error(msg)
            raise MCPClientError(msg) from None
        except asyncio.CancelledError:
            await stack.aclose()
            raise
        except Exception as exc:
            await stack.aclose()
            safe_msg = redact_secrets(str(exc))
            logger.error("Failed to connect %s: %s", self.client_name, safe_msg)
            raise MCPClientError(f"Failed to connect {self.client_name}: {safe_msg}") from exc

    async def disconnect(self) -> None:
        """Terminate the stdio session and clean up background subprocess resources."""
        self._is_connected = False
        self._session = None
        self._discovered_tools.clear()
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as exc:
                logger.debug("Error while disconnecting %s: %s", self.client_name, exc)
            finally:
                self._exit_stack = None

    async def __aenter__(self) -> "BaseMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    async def discover_tools(self) -> list[mcp_types.Tool]:
        """Query the remote MCP server for registered tools and update local cache."""
        if not self.is_connected or not self._session:
            msg = f"{self.client_name} is not connected. Call connect() first."
            raise MCPClientError(msg)

        try:
            async with asyncio.timeout(self.timeout):
                tools_res = await self._session.list_tools()

            self._discovered_tools = {tool.name: tool for tool in tools_res.tools}
            logger.info(
                "%s discovered %d tools: %s",
                self.client_name,
                len(self._discovered_tools),
                list(self._discovered_tools.keys()),
            )
            return list(self._discovered_tools.values())
        except TimeoutError:
            msg = f"{self.client_name} tool discovery timed out after {self.timeout}s"
            raise MCPClientError(msg) from None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            safe_msg = redact_secrets(str(exc))
            raise MCPClientError(
                f"Tool discovery failed on {self.client_name}: {safe_msg}"
            ) from exc

    def get_tool(self, tool_name: str) -> mcp_types.Tool | None:
        """Retrieve a cached tool definition by name."""
        return self._discovered_tools.get(tool_name)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Invoke an MCP tool by name with arguments and return its parsed result."""
        if not self.is_connected or not self._session:
            msg = f"{self.client_name} is not connected. Cannot invoke '{name}'."
            raise MCPClientError(msg)

        effective_timeout = timeout or self.timeout
        safe_args = arguments or {}

        try:
            async with asyncio.timeout(effective_timeout):
                res: mcp_types.CallToolResult = await self._session.call_tool(
                    name=name,
                    arguments=safe_args,
                )

            # Process output content blocks
            output_parts: list[str] = []
            if res.content:
                for block in res.content:
                    if hasattr(block, "text"):
                        output_parts.append(block.text)
                    elif hasattr(block, "data"):
                        output_parts.append(str(block.data))

            full_text = "\n".join(output_parts)
            safe_text = redact_secrets(full_text)

            if res.is_error:
                logger.error(
                    "Tool '%s' returned error on %s: %s",
                    name,
                    self.client_name,
                    safe_text,
                )
                raise MCPToolExecutionError(f"Tool '{name}' error: {safe_text}")

            # Attempt JSON parse of output payload, fallback to raw text
            if safe_text.strip():
                try:
                    return json.loads(safe_text)
                except json.JSONDecodeError:
                    return safe_text
            return {}

        except TimeoutError:
            msg = f"Tool '{name}' execution on {self.client_name} timed out after {effective_timeout}s"
            logger.error(msg)
            raise TimeoutError(msg) from None
        except asyncio.CancelledError:
            raise
        except MCPToolExecutionError:
            raise
        except Exception as exc:
            safe_msg = redact_secrets(str(exc))
            logger.error("Tool execution failed for '%s': %s", name, safe_msg)
            raise MCPClientError(f"Execution of '{name}' failed: {safe_msg}") from exc
