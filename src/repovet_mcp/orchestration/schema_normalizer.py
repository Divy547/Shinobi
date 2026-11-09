"""JSON Schema normalization utility for Google Gemini OpenAPI 3.0 compatibility."""

import copy
from typing import Any

# OpenAPI 3.0 supported primitive types
VALID_OPENAPI_TYPES = frozenset({"string", "number", "integer", "boolean", "array", "object"})

# Keywords unsupported or rejected by Gemini API in tool function declarations
STRIPPED_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$defs",
        "definitions",
        "title",
        "additionalProperties",
    }
)


def _resolve_refs(schema: Any, defs: dict[str, Any]) -> Any:
    """Recursively resolve local $ref pointers against definition dictionaries."""
    if isinstance(schema, dict):
        if "$ref" in schema and isinstance(schema["$ref"], str):
            ref_path = schema["$ref"]
            ref_name = ref_path.split("/")[-1]
            if ref_name in defs:
                resolved = copy.deepcopy(defs[ref_name])
                # Recursively resolve any nested refs inside the resolved definition
                return _resolve_refs(resolved, defs)
            return {"type": "object"}

        return {k: _resolve_refs(v, defs) for k, v in schema.items()}

    if isinstance(schema, list):
        return [_resolve_refs(item, defs) for item in schema]

    return schema


def normalize_schema_for_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively normalize a standard MCP/Pydantic JSON schema into a clean OpenAPI 3.0 schema.

    - Resolves local $defs and $ref pointers.
    - Simplifies nullable anyOf/oneOf constructs (e.g. [{'type': 'string'}, {'type': 'null'}])
      into a single typed property with `nullable: True`.
    - Strips unsupported metadata ($schema, $id, $defs, title, additionalProperties).
    - Preserves types, descriptions, required fields, arrays, and nested object properties.
    """
    if not isinstance(schema, dict):
        return {"type": "object"}

    # Extract definitions for ref resolution
    defs: dict[str, Any] = {}
    if "$defs" in schema and isinstance(schema["$defs"], dict):
        defs.update(schema["$defs"])
    if "definitions" in schema and isinstance(schema["definitions"], dict):
        defs.update(schema["definitions"])

    # Resolve all refs upfront
    working_schema = _resolve_refs(copy.deepcopy(schema), defs)

    def _normalize_node(node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        normalized: dict[str, Any] = {}
        is_nullable = False

        # Handle anyOf / oneOf (frequently emitted by Pydantic v2 for Optional[T] / Union)
        union_branches = node.get("anyOf") or node.get("oneOf")
        if isinstance(union_branches, list):
            non_null_branches: list[dict[str, Any]] = []
            for branch in union_branches:
                if isinstance(branch, dict):
                    if branch.get("type") == "null":
                        is_nullable = True
                    else:
                        non_null_branches.append(branch)

            if non_null_branches:
                # Merge the primary non-null branch into current node
                primary_branch = _normalize_node(non_null_branches[0])
                if isinstance(primary_branch, dict):
                    normalized.update(primary_branch)
            else:
                normalized["type"] = "string"

        # Handle allOf (inheritance / composition)
        elif "allOf" in node and isinstance(node["allOf"], list):
            for sub_schema in node["allOf"]:
                norm_sub = _normalize_node(sub_schema)
                if isinstance(norm_sub, dict):
                    if "properties" in norm_sub:
                        normalized.setdefault("properties", {}).update(norm_sub["properties"])
                    if "required" in norm_sub and isinstance(norm_sub["required"], list):
                        normalized.setdefault("required", []).extend(norm_sub["required"])
                    for k, v in norm_sub.items():
                        if k not in ("properties", "required"):
                            normalized[k] = v

        # Copy and clean attributes
        for key, value in node.items():
            if key in STRIPPED_KEYWORDS or key in ("anyOf", "oneOf", "allOf"):
                continue

            # Strip default: null to avoid Gemini OpenAPI 3.0 parsing errors
            if key == "default" and value is None:
                is_nullable = True
                continue

            normalized[key] = value

        # Set nullable flag if detected
        if is_nullable:
            normalized["nullable"] = True

        # Ensure valid lowercase OpenAPI type
        if "type" in normalized and isinstance(normalized["type"], str):
            t_lower = normalized["type"].lower()
            if t_lower in VALID_OPENAPI_TYPES:
                normalized["type"] = t_lower
            elif t_lower == "null":
                normalized["type"] = "string"
                normalized["nullable"] = True
            else:
                normalized["type"] = "object"
        elif "properties" in normalized:
            normalized["type"] = "object"

        # Recursively process object properties
        if "properties" in normalized and isinstance(normalized["properties"], dict):
            clean_props: dict[str, Any] = {}
            for prop_name, prop_def in normalized["properties"].items():
                clean_props[prop_name] = _normalize_node(prop_def)
            normalized["properties"] = clean_props

            # Clean required list: keep only properties that exist
            if "required" in normalized and isinstance(normalized["required"], list):
                valid_required = [r for r in normalized["required"] if r in clean_props]
                if valid_required:
                    normalized["required"] = valid_required
                else:
                    normalized.pop("required", None)

        # Recursively process array items
        if "items" in normalized and isinstance(normalized["items"], dict):
            normalized["items"] = _normalize_node(normalized["items"])

        return normalized

    result = _normalize_node(working_schema)
    if not isinstance(result, dict) or "type" not in result:
        return {"type": "object", "properties": {}}

    return result
