"""Cross-domain import directionality boundary (DD5).

Makes D9's prohibition ("`ai` imports nothing; nothing imports `content`")
executable for the first time. A separate module from
`test_domain_boundary.py`: that one has a single scoped responsibility
(purity of `domain/`) and only walks `domain/`; this one walks all three
layers (`domain/`, `application/`, `infrastructure/`) of every domain and
checks the *direction* of cross-domain imports, not their purity.

`gcell/api/` is the composition root and is exempt by design -- it imports
everything and is not itself a domain.

Verified green against today's tree before this test existed (design.md
DD5): the only cross-domain imports in `backend/src/gcell/**` were
`stock -> products` (4 modules) and everything -> `shared`; `shared`
imports no domain. Uses Python's `ast` module (real `Import`/`ImportFrom`
statements), same technique as `test_domain_boundary.py`.
"""

import ast
from pathlib import Path

# The fixed dependency direction (D9 / DD5). Every domain may ALSO always
# import `shared` -- that is handled separately below, not listed per-key,
# so `shared` itself (which must import NO domain, not even implicitly)
# stays an honest `set()`.
ALLOWED_EDGES: dict[str, set[str]] = {
    "products": set(),
    "stock": {"products"},
    "content": {"ai", "products"},
    "ai": set(),
    "recommendation": set(),
    "shared": set(),
}

DOMAINS = list(ALLOWED_EDGES)

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src" / "gcell"


def _iter_domain_python_files(domain: str) -> list[Path]:
    domain_dir = BACKEND_SRC / domain
    assert domain_dir.is_dir(), f"missing domain directory: {domain_dir}"
    return sorted(
        path
        for path in domain_dir.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _imported_domains(file_path: Path) -> set[str]:
    """Return every top-level `gcell.<domain>...` package this file
    imports from (excluding `gcell.api`, which is not a domain).
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imported: set[str] = set()

    for node in ast.walk(tree):
        module_path: str | None = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_path = alias.name
                parts = module_path.split(".")
                if len(parts) >= 2 and parts[0] == "gcell":
                    imported.add(parts[1])
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 2 and parts[0] == "gcell":
                imported.add(parts[1])

    return imported


def test_cross_domain_imports_match_allowed_edges() -> None:
    offenders: dict[str, set[str]] = {}

    for domain in DOMAINS:
        # Every domain may import `shared` (design.md DD5); `shared`
        # importing `shared` is a same-domain import, filtered out below,
        # so this addition never grants `shared` a self-edge.
        allowed = ALLOWED_EDGES[domain] | {"shared"}

        for file_path in _iter_domain_python_files(domain):
            imported = _imported_domains(file_path)
            # Same-domain imports and `gcell.api` (composition root,
            # exempt by design) are not cross-domain edges.
            disallowed = imported - allowed - {domain, "api"}
            if disallowed:
                offenders[str(file_path)] = disallowed

    assert not offenders, (
        "cross-domain import direction violates ALLOWED_EDGES (D9/DD5): "
        f"{offenders}"
    )
