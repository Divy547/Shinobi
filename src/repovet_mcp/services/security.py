"""Security, sanitization, and input validation utilities for RepoVet MCP."""

import html
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

# Strict regex patterns for identifiers
AUDIT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
REPO_COMPONENT_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{1,100}$")

# Patterns for sensitive tokens and credentials
TOKEN_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9_]{15,}"),
    re.compile(r"gho_[a-zA-Z0-9_]{15,}"),
    re.compile(r"ghu_[a-zA-Z0-9_]{15,}"),
    re.compile(r"ghs_[a-zA-Z0-9_]{15,}"),
    re.compile(r"ghr_[a-zA-Z0-9_]{15,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{15,}"),
    re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(
        r"(?:token|secret|password|api[_\-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?",
        re.IGNORECASE,
    ),
]

# Set of dynamic runtime secrets registered for scrubbing
_DYNAMIC_SECRETS: set[str] = set()


def register_secret_for_redaction(secret: str | None) -> None:
    """Register an active runtime secret (e.g. API key or PAT) for automatic scrubbing."""
    if secret:
        clean = secret.strip()
        if len(clean) >= 6:
            _DYNAMIC_SECRETS.add(clean)


def unregister_secret_for_redaction(secret: str | None) -> None:
    """Unregister an active runtime secret."""
    if secret:
        _DYNAMIC_SECRETS.discard(secret.strip())


def clear_registered_secrets() -> None:
    """Clear all dynamically registered secrets."""
    _DYNAMIC_SECRETS.clear()


def redact_secrets(
    text: str, extra_secrets: list[str] | set[str] | frozenset[str] | None = None
) -> str:
    """Mask known sensitive tokens, keys, authorization headers, and registered secrets in strings."""
    if not text:
        return ""
    sanitized = str(text)

    # Scrub dynamically registered secrets first
    all_dynamic = _DYNAMIC_SECRETS.union(extra_secrets or ())
    for secret in all_dynamic:
        if secret and len(secret) >= 6 and secret in sanitized:
            sanitized = sanitized.replace(secret, "[REDACTED_SECRET]")

    # Scrub regex patterns
    for pattern in TOKEN_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


# Whitelist of standard, non-sensitive environment variable names to preserve in child subprocesses
SAFE_ENV_PASSTHROUGH_VARS = frozenset(
    {
        "PATH",
        "HOME",
        "TMPDIR",
        "TEMP",
        "TMP",
        "USER",
        "LOGNAME",
        "SHELL",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "SYSTEMROOT",
        "COMSPEC",
        "PATHEXT",
        "VIRTUAL_ENV",
        "NODE_PATH",
        "PYTHONPATH",
    }
)

# Sensitive substrings that must NEVER be passed from the host environment to child MCP processes
SENSITIVE_ENV_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "AUTH",
    "PASS",
    "CREDENTIAL",
    "AWS_",
    "GCP_",
    "AZURE_",
    "GEMINI_",
)


def build_isolated_subprocess_env(
    custom_env: dict[str, str] | None = None,
    allowed_passthrough: set[str] | frozenset[str] | None = None,
) -> dict[str, str]:
    """Construct a minimal, isolated environment for child MCP subprocesses.

    Preserves safe runtime essentials (PATH, HOME, temporary directory) while strictly
    filtering out host ambient secrets (e.g. GEMINI_API_KEY, AWS tokens, cloud credentials).

    NOTE: Process environment variables may still be inspectable by local users with
    sufficient privileges (e.g., via /proc/<pid>/environ on Linux). Sensitive credentials
    should be protected through process isolation and least-privilege token scoping.
    """
    import os

    passthrough_keys = allowed_passthrough or SAFE_ENV_PASSTHROUGH_VARS
    isolated_env: dict[str, str] = {}

    for key, val in os.environ.items():
        if key in passthrough_keys:
            key_upper = key.upper()
            if not any(sub in key_upper for sub in SENSITIVE_ENV_SUBSTRINGS):
                isolated_env[key] = val

    # Overlay explicitly provided custom variables intended specifically for this child process
    if custom_env:
        for k, v in custom_env.items():
            if v is not None:
                isolated_env[k] = str(v)

    return isolated_env


def sanitize_unicode_for_pdf(text: str) -> str:
    """Safely replace characters unsupported by standard PDF fonts with readable fallbacks.

    - Emoji & pictographs are mapped to their Unicode name: e.g. 🚀 -> [rocket]
    - CJK ideographs/scripts are mapped to hex codepoints: e.g. 世 -> [U+4E16]
    - Accented Latin, Greek, and Cyrillic characters are preserved for TrueType rendering.
    - Zero-width joiners and variation selectors are safely ignored.
    """
    result: list[str] = []
    for c in text:
        cp = ord(c)
        # Drop variation selectors and zero-width joiners
        if 0xFE00 <= cp <= 0xFE0F or cp == 0x200D:
            continue

        try:
            uname = unicodedata.name(c, "")
        except Exception:
            uname = ""

        # CJK scripts & ideographs (Unified Ideographs, Hangul, Kana, Bopomofo, etc.)
        if (
            0x2E80 <= cp <= 0x2FD5
            or 0x3040 <= cp <= 0x30FF
            or 0x3105 <= cp <= 0x312F
            or 0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF
            or 0xF900 <= cp <= 0xFAFF
            or 0xAC00 <= cp <= 0xD7AF
            or 0x20000 <= cp <= 0x2CEAF
            or uname.startswith(("CJK", "HANGUL", "HIRAGANA", "KATAKANA", "BOPOMOFO"))
        ):
            result.append(f"[U+{cp:04X}]")
        # Emoji and pictographs
        elif (
            0x1F300 <= cp <= 0x1FAFF
            or 0x1F600 <= cp <= 0x1F64F
            or 0x1F680 <= cp <= 0x1F6FF
            or 0x2600 <= cp <= 0x27BF
            or 0x2B50 <= cp <= 0x2B55
            or (unicodedata.category(c) == "So" and cp > 0x2000)
        ):
            name = uname.lower() if uname else f"u+{cp:04x}"
            result.append(f"[{name}]")
        else:
            result.append(c)

    return "".join(result)


def sanitize_for_report(text: object | None) -> str:
    """Escape HTML/XML markup, sanitize unsupported Unicode, and strip control characters for ReportLab."""
    if text is None:
        return "N/A"
    raw_str = str(text)
    # Remove ASCII control characters except newline and tab
    clean_chars = "".join(c for c in raw_str if c in ("\n", "\t") or ord(c) >= 32)
    # Sanitize unsupported Unicode (emoji to [name], CJK to [U+XXXX])
    sanitized_unicode = sanitize_unicode_for_pdf(clean_chars)
    # XML escape to prevent ReportLab markup injection
    return html.escape(sanitized_unicode, quote=True)


def validate_audit_id(audit_id: str) -> str:
    """Validate that an audit ID is well-formed, non-empty, and free of path traversal."""
    if not audit_id or not isinstance(audit_id, str):
        msg = "Audit ID must be a non-empty string."
        raise ValueError(msg)
    clean = audit_id.strip()
    if not AUDIT_ID_REGEX.match(clean):
        msg = (
            f"Invalid audit ID '{clean}'. Must be 1-128 alphanumeric characters, "
            "hyphens, or underscores with no path separators or special symbols."
        )
        raise ValueError(msg)
    return clean


def validate_repo_component(name: str, component_type: str = "identifier") -> str:
    """Validate a repository owner or repository name component."""
    if not name or not isinstance(name, str):
        msg = f"Repository {component_type} must be a non-empty string."
        raise ValueError(msg)
    clean = name.strip()
    if (
        clean in (".", "..")
        or "/" in clean
        or "\\" in clean
        or not REPO_COMPONENT_REGEX.match(clean)
    ):
        msg = (
            f"Invalid repository {component_type} '{clean}'. "
            "Must be 1-100 characters containing only alphanumeric, hyphens, underscores, or dots."
        )
        raise ValueError(msg)
    return clean


def validate_repository_url_domain(
    url: str, allowed_hosts: tuple[str, ...] = ("github.com", "www.github.com")
) -> str:
    """Validate that an external repository URL belongs to an authorized GitHub domain."""
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").lower()
    if hostname not in allowed_hosts:
        msg = (
            f"Invalid repository URL host '{hostname}'. Only authorized GitHub domains "
            f"({', '.join(allowed_hosts)}) are permitted to prevent SSRF."
        )
        raise ValueError(msg)
    return hostname


def validate_safe_subpath(base_dir: Path, subpath: str) -> Path:
    """Ensure a resolved subpath resides strictly within the specified base directory."""
    base_resolved = base_dir.resolve()
    target_resolved = (base_dir / subpath).resolve()
    if not target_resolved.is_relative_to(base_resolved) or target_resolved == base_resolved:
        msg = f"Path traversal attempt detected: '{subpath}' attempts to access outside base directory."
        raise ValueError(msg)
    return target_resolved
