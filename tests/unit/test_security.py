"""Unit tests for security, sanitization, secret redaction, and input validation."""

from pathlib import Path

import pytest

from repovet_mcp.services.security import (
    clear_registered_secrets,
    redact_secrets,
    register_secret_for_redaction,
    sanitize_for_report,
    unregister_secret_for_redaction,
    validate_audit_id,
    validate_repo_component,
    validate_repository_url_domain,
    validate_safe_subpath,
)


def test_redact_secrets() -> None:
    """Verify secrets and authentication tokens are masked."""
    # GitHub personal access tokens
    text1 = "Error connecting with token ghp_123456789012345678901234567890 in URL"
    assert redact_secrets(text1) == "Error connecting with token [REDACTED_SECRET] in URL"

    # Fine-grained personal access tokens
    text2 = "Using github_pat_11AABBCCDDEEFFGG123456789_xyz for API access"
    assert redact_secrets(text2) == "Using [REDACTED_SECRET] for API access"

    # Bearer tokens
    text3 = "Authorization: Bearer my_secret_bearer_token_12345"
    assert redact_secrets(text3) == "Authorization: [REDACTED_SECRET]"

    # API key assignments
    text4 = "api_key='abcdef1234567890'"
    assert redact_secrets(text4) == "[REDACTED_SECRET]"

    # None and empty strings
    assert redact_secrets("") == ""


def test_dynamic_secret_redaction() -> None:
    """Verify dynamically registered secrets are redacted and cleared appropriately."""
    custom_secret = "super_confidential_session_key_998877"
    try:
        register_secret_for_redaction(custom_secret)
        msg = f"Connecting using key {custom_secret} on host"
        assert redact_secrets(msg) == "Connecting using key [REDACTED_SECRET] on host"

        # Short secrets (<6 chars) are ignored
        register_secret_for_redaction("abc")
        msg2 = "Short abc secret"
        assert redact_secrets(msg2) == "Short abc secret"

        # Extra secrets in redact_secrets
        assert (
            redact_secrets("Token custom_one_time_key_44", extra_secrets={"custom_one_time_key_44"})
            == "Token [REDACTED_SECRET]"
        )

        # Unregistering secret
        unregister_secret_for_redaction(custom_secret)
        assert redact_secrets(msg) == msg
    finally:
        clear_registered_secrets()


def test_sanitize_for_report() -> None:
    """Verify ReportLab markup injection characters and control chars are safely sanitized."""
    # XML tags and special characters
    raw = "<script>alert('xss')</script> & <foo attr=\"bar\">"
    sanitized = sanitize_for_report(raw)
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert "&lt;script&gt;" in sanitized
    assert "&amp;" in sanitized
    assert "&quot;bar&quot;" in sanitized

    # Control characters stripped
    with_control = "Safe text\x00\x08\x1b\x1fwith control chars"
    clean = sanitize_for_report(with_control)
    assert "\x00" not in clean
    assert "\x1b" not in clean
    assert "Safe textwith control chars" in clean

    # None returns N/A
    assert sanitize_for_report(None) == "N/A"


def test_sanitize_for_report_unicode_handling() -> None:
    """Verify Emoji -> [name], CJK -> [U+XXXX], and accented Latin characters are preserved."""
    # Emojis converted to [name]
    emoji_str = "Deploying 🚀 with sparkles ✨ and fire 🔥"
    res_emoji = sanitize_for_report(emoji_str)
    assert "[rocket]" in res_emoji
    assert "[sparkles]" in res_emoji
    assert "[fire]" in res_emoji
    assert "🚀" not in res_emoji

    # CJK characters converted to [U+XXXX]
    cjk_str = "Japanese 日本語 and Chinese 世界"
    res_cjk = sanitize_for_report(cjk_str)
    assert "[U+65E5][U+672C][U+8A9E]" in res_cjk
    assert "[U+4E16][U+754C]" in res_cjk
    assert "日本語" not in res_cjk
    assert "世界" not in res_cjk

    # Accented Latin characters preserved
    latin_str = "Café, naïve, façade, Schrödinger, résumé"
    res_latin = sanitize_for_report(latin_str)
    assert "Café" in res_latin
    assert "naïve" in res_latin
    assert "façade" in res_latin
    assert "Schrödinger" in res_latin
    assert "résumé" in res_latin


def test_validate_audit_id() -> None:
    """Verify audit ID syntax enforcement and path traversal prevention."""
    # Valid audit IDs
    assert validate_audit_id("audit_owner_repo_1700000000") == "audit_owner_repo_1700000000"
    assert validate_audit_id("audit-123-ABC_xyz") == "audit-123-ABC_xyz"

    # Path traversal attempts
    with pytest.raises(ValueError, match="Invalid audit ID"):
        validate_audit_id("../etc/passwd")

    with pytest.raises(ValueError, match="Invalid audit ID"):
        validate_audit_id("audit/subpath")

    with pytest.raises(ValueError, match="Invalid audit ID"):
        validate_audit_id("..\\windows\\system32")

    # Empty or whitespace
    with pytest.raises(ValueError, match="Audit ID must be a non-empty string"):
        validate_audit_id("")

    with pytest.raises(ValueError, match="Invalid audit ID"):
        validate_audit_id("   ")


def test_validate_repo_component() -> None:
    """Verify repository owner and repo names conform to safe format."""
    assert validate_repo_component("pallets", "owner") == "pallets"
    assert validate_repo_component("flask-api.v2", "repo") == "flask-api.v2"

    with pytest.raises(ValueError, match="Invalid repository owner"):
        validate_repo_component(".", "owner")

    with pytest.raises(ValueError, match="Invalid repository repo"):
        validate_repo_component("..", "repo")

    with pytest.raises(ValueError, match="Invalid repository repo"):
        validate_repo_component("repo/with/slash", "repo")


def test_validate_repository_url_domain_ssrf_prevention() -> None:
    """Verify domain whitelisting blocks SSRF attempts."""
    # Legitimate GitHub domains
    assert validate_repository_url_domain("https://github.com/owner/repo") == "github.com"
    assert validate_repository_url_domain("http://www.github.com/owner/repo") == "www.github.com"
    assert validate_repository_url_domain("https://github.com:443/owner/repo") == "github.com"

    # Malicious or internal IP SSRF attempts
    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        validate_repository_url_domain("https://127.0.0.1/owner/repo")

    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        validate_repository_url_domain("https://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        validate_repository_url_domain("https://attacker-github.com/owner/repo")

    with pytest.raises(ValueError, match="Only authorized GitHub domains"):
        validate_repository_url_domain("https://evil.org/owner/repo")


def test_validate_safe_subpath_traversal() -> None:
    """Verify path traversal resolution strictly enforces base directory confinement."""
    base = Path("/tmp/repovet_test_dir").resolve()

    # Safe subpath
    safe_target = validate_safe_subpath(base, "subfolder/file.json")
    assert safe_target == base / "subfolder" / "file.json"

    # Traversal escaping base directory
    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        validate_safe_subpath(base, "../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        validate_safe_subpath(base, "/etc/shadow")
