"""Hexagonal domain-boundary safety net.

Walks the AST of every `.py` file under each of the 6 domains' `domain/`
layer and asserts that none of them import a banned framework/infrastructure
package (FastAPI, Pydantic, Supabase, SQLAlchemy, httpx). `domain/` must stay
pure Python (stdlib + same-domain `domain` code only) so business rules never
depend on a web framework, an ORM, or a network client.

Uses Python's `ast` module to inspect real `Import`/`ImportFrom` statements —
not string/regex matching — so a banned name inside a docstring, comment, or
string literal never produces a false positive.
"""

import ast
from pathlib import Path

DOMAINS = ["products", "stock", "content", "ai", "recommendation", "shared"]
BANNED_MODULES = {"fastapi", "pydantic", "supabase", "sqlalchemy", "httpx", "asyncpg"}

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src" / "gcell"


def _iter_domain_python_files() -> list[Path]:
    files: list[Path] = []
    for domain in DOMAINS:
        domain_dir = BACKEND_SRC / domain / "domain"
        assert domain_dir.is_dir(), f"missing domain layer directory: {domain_dir}"
        files.extend(sorted(domain_dir.rglob("*.py")))
    return files


def _banned_imports_in_file(file_path: Path) -> list[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in BANNED_MODULES:
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in BANNED_MODULES:
                    violations.append(node.module)

    return violations


def test_domain_layers_import_no_framework_or_infra_packages() -> None:
    offenders: dict[str, list[str]] = {}

    for file_path in _iter_domain_python_files():
        violations = _banned_imports_in_file(file_path)
        if violations:
            offenders[str(file_path)] = violations

    assert not offenders, (
        "domain/ layer must not import framework/infrastructure packages "
        f"{sorted(BANNED_MODULES)}, found violations: {offenders}"
    )
