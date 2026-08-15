"""Unit tests for `gcell.api.admin._execute_or_raise`'s exception -> HTTP
status mapping.

Calls the mapper directly with a raising coroutine -- no `TestClient`, no
router, no auth -- the fastest layer that can prove the mapping itself
(design.md Testing Strategy "Unit -- mapper"). The existing coverage for
this function lives in `tests/integration/api/test_admin.py` /
`test_admin_images.py` only indirectly, through full HTTP round-trips; this
file is the first direct unit test of the mapper and stays free to grow
with future mapping cases.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from gcell.api.admin import _execute_or_raise
from gcell.stock.application.exceptions import UnknownVariantError


async def _raise(exc: Exception):
    raise exc


async def test_unknown_variant_error_maps_to_404_not_found() -> None:
    # Decision 3: unreachable end-to-end once the use-case-layer ownership
    # guard exists (spec admin-api-access "Unknown Variant Errors Map To
    # 404"), so it is proven here as defense-in-depth instead.
    with pytest.raises(HTTPException) as excinfo:
        await _execute_or_raise(_raise(UnknownVariantError(uuid4())))

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "not_found"
