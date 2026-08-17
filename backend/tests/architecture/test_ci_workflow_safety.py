"""CI workflow shell-injection and secret-exposure boundary.

Reads `.github/workflows/ci.yml` as text and asserts the properties the
design.md Threat Matrix names as load-bearing for a repo's first-ever CI
shell execution surface:

- no `${{ secrets.` token anywhere (D2: zero GitHub Secrets in this change)
- no secret-shaped literal (an `sk-...` style token, or a long hex/base64
  string) pasted into the file by mistake
- no `pull_request_target` trigger (would hand a fork PR a write token)
- `permissions:` is declared explicitly (no implicit default write token)
- no `${{ github.event` / `${{ github.head_ref }}` interpolated inside any
  `run:` shell block (the classic GitHub Actions script-injection vector)
- the placeholder `NEXT_PUBLIC_SUPABASE_URL` is a loopback address, never a
  `*.supabase.co` hostname, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` is not a real
  (JWT-shaped) key

Mirrors `test_frontend_service_role_boundary.py`'s static-text-check idiom:
this is a text/regex boundary test, not a YAML-semantics test.
"""

import re
from pathlib import Path

CI_WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

_RUN_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)run:\s*(?P<inline>.*)$")

_SECRET_SHAPED_RE = re.compile(
    r"sk-[A-Za-z0-9]{16,}"  # e.g. an OpenAI/Stripe-style secret key
    r"|[0-9a-fA-F]{32,}"  # long hex blob
    r"|[A-Za-z0-9+/]{40,}={0,2}"  # long base64 blob
)

_JWT_SHAPED_RE = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _read_workflow() -> str:
    assert CI_WORKFLOW.is_file(), f"missing CI workflow file: {CI_WORKFLOW}"
    return CI_WORKFLOW.read_text(encoding="utf-8")


def _extract_run_blocks(text: str) -> list[str]:
    """Return the raw text of every step's `run:` value (inline or block)."""
    lines = text.splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        match = _RUN_LINE_RE.match(lines[i])
        if match is None:
            i += 1
            continue

        indent = len(match.group("indent"))
        inline = match.group("inline").strip()
        block_lines: list[str] = []
        if inline and inline not in {"|", ">", "|-", ">-", "|+", ">+"}:
            block_lines.append(inline)
        i += 1

        while i < len(lines):
            next_line = lines[i]
            if next_line.strip() == "":
                block_lines.append(next_line)
                i += 1
                continue
            next_indent = len(next_line) - len(next_line.lstrip(" \t"))
            if next_indent > indent:
                block_lines.append(next_line)
                i += 1
            else:
                break

        blocks.append("\n".join(block_lines))

    return blocks


def _extract_env_value(text: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def test_ci_workflow_never_references_github_secrets() -> None:
    text = _read_workflow()

    assert "${{ secrets." not in text, (
        "ci.yml must use zero GitHub Secrets in this change (D2); "
        "found a '${{ secrets.' reference"
    )


def test_ci_workflow_contains_no_secret_shaped_literals() -> None:
    text = _read_workflow()

    offenders = [match.group(0) for match in _SECRET_SHAPED_RE.finditer(text)]

    assert not offenders, (
        "ci.yml must not contain a secret-shaped literal (sk-... token, or a "
        f"long hex/base64 blob), found: {offenders}"
    )


def test_ci_workflow_never_uses_pull_request_target_trigger() -> None:
    text = _read_workflow()

    assert "pull_request_target" not in text, (
        "ci.yml must never use the 'pull_request_target' trigger -- it grants "
        "a fork PR a write token and secret access"
    )


def test_ci_workflow_declares_explicit_permissions() -> None:
    text = _read_workflow()

    assert re.search(r"^permissions:\s*$", text, flags=re.MULTILINE), (
        "ci.yml must declare a top-level 'permissions:' key explicitly "
        "rather than relying on the implicit default token"
    )


def test_ci_workflow_run_blocks_never_interpolate_github_event_data() -> None:
    text = _read_workflow()

    offenders = [
        block
        for block in _extract_run_blocks(text)
        if "${{ github.event" in block or "${{ github.head_ref" in block
    ]

    assert not offenders, (
        "no 'run:' shell block may interpolate '${{ github.event...}}' or "
        f"'${{ github.head_ref }}' directly -- this is a known GitHub "
        f"Actions script-injection vector, found in: {offenders}"
    )


def test_ci_workflow_supabase_placeholders_are_safe_local_dev_values() -> None:
    text = _read_workflow()

    url = _extract_env_value(text, "NEXT_PUBLIC_SUPABASE_URL")
    assert url is not None, "ci.yml must set NEXT_PUBLIC_SUPABASE_URL for the frontend build"
    assert url.startswith("http://127.0.0.1"), (
        f"NEXT_PUBLIC_SUPABASE_URL must be a loopback placeholder, got: {url}"
    )
    assert "supabase.co" not in url, (
        f"NEXT_PUBLIC_SUPABASE_URL must never point at a real Supabase project, got: {url}"
    )

    anon_key = _extract_env_value(text, "NEXT_PUBLIC_SUPABASE_ANON_KEY")
    assert anon_key is not None, (
        "ci.yml must set NEXT_PUBLIC_SUPABASE_ANON_KEY for the frontend build"
    )
    assert not _JWT_SHAPED_RE.match(anon_key), (
        f"NEXT_PUBLIC_SUPABASE_ANON_KEY must be a placeholder, not a real "
        f"JWT-shaped Supabase key, got: {anon_key}"
    )
