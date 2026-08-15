"""Frontend service-role-key leak boundary.

Walks every file under `frontend/src/` and asserts none of them reference
`SERVICE_ROLE` — the Supabase service_role key (`SUPABASE_SERVICE_ROLE_KEY`,
`config.py`) must stay backend-only. A `NEXT_PUBLIC_`-prefixed twin, or any
other frontend reference to the raw key name, would ship it to the browser.
design.md's "Config" section (admin-product-images) commits to this exact
guardrail.
"""

from pathlib import Path

FRONTEND_SRC = Path(__file__).resolve().parents[3] / "frontend" / "src"

_SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2", ".ttf"}


def _iter_frontend_files() -> list[Path]:
    assert FRONTEND_SRC.is_dir(), f"missing frontend src directory: {FRONTEND_SRC}"
    return [
        path
        for path in FRONTEND_SRC.rglob("*")
        if path.is_file() and path.suffix not in _SKIP_SUFFIXES
    ]


def test_frontend_src_never_references_service_role_key() -> None:
    offenders: list[str] = []

    for file_path in _iter_frontend_files():
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        if "SERVICE_ROLE" in text:
            offenders.append(str(file_path))

    assert not offenders, (
        "frontend/src/ must never reference SERVICE_ROLE (the Supabase "
        f"service_role key is backend-only), found in: {offenders}"
    )
