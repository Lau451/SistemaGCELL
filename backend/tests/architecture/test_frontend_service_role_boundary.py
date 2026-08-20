"""Frontend service-role-key / Gemini-key leak boundary.

Walks every file under `frontend/src/` and asserts none of them reference
`SERVICE_ROLE` — the Supabase service_role key (`SUPABASE_SERVICE_ROLE_KEY`,
`config.py`) must stay backend-only. A `NEXT_PUBLIC_`-prefixed twin, or any
other frontend reference to the raw key name, would ship it to the browser.
design.md's "Config" section (admin-product-images) commits to this exact
guardrail.

Parametrized over `("SERVICE_ROLE", "GEMINI")` (content-ai-domains design.md
DD4/Threat Matrix "Secret exposure"): `GEMINI_API_KEY` is the first
non-Supabase secret this repo introduces and MUST stay backend-only for the
identical reason — this is a regression guard for every PR that touches
`frontend/src/app/(admin)/admin/products/` (Phase 3/5/11's diffs), proving
none of them ever reference `GEMINI` even though this PR (6) ships zero
frontend code itself.
"""

from pathlib import Path

import pytest

FRONTEND_SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"

_SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2", ".ttf"}


def _iter_frontend_files() -> list[Path]:
    assert FRONTEND_SRC.is_dir(), f"missing frontend src directory: {FRONTEND_SRC}"
    return [
        path
        for path in FRONTEND_SRC.rglob("*")
        if path.is_file() and path.suffix not in _SKIP_SUFFIXES
    ]


@pytest.mark.parametrize("banned_token", ["SERVICE_ROLE", "GEMINI"])
def test_frontend_src_never_references_banned_secret_token(banned_token: str) -> None:
    offenders: list[str] = []

    for file_path in _iter_frontend_files():
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if banned_token in text:
            offenders.append(str(file_path))

    assert not offenders, (
        f"frontend/src/ must never reference {banned_token} (that secret is "
        f"backend-only), found in: {offenders}"
    )
