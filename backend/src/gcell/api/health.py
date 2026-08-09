"""Liveness route. No auth, no DB dependency — must stay green before
Supabase (or any other backing service) exists.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
