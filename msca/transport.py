"""MSCA transport — transport utilities.

Enhanced transport layer integrating store, glyphs, and ECT
for reliable data transport with error correction.
"""

from __future__ import annotations

from typing import Any

from . import ect, glyph, store

__all__ = ["TransportError", "pack", "unpack", "pack_with_correction",
           "unpack_with_correction"]


class TransportError(Exception):
    """Transport error."""


def pack(obj: Any) -> str:
    """Pack object into a transport handle."""
    return glyph.build(obj)


def unpack(handle: str) -> str:
    """Unpack from handle."""
    return store.resolve(handle)


def pack_with_correction(obj: Any, parity_ratio: float = 0.125) -> dict[str, Any]:
    """Pack with ECT error correction."""
    h = glyph.build(obj)
    content = store.resolve(h).encode('utf-8')
    block = ect.ect_encode(content, parity_ratio=parity_ratio)
    corr_h = glyph.build({
        'data_handle': h,
        'checksum': block.checksum,
        'parity_len': len(block.parity),
    })
    return {
        'handle': h,
        'correction_handle': corr_h,
        'checksum': block.checksum,
        'verified': ect.ect_verify(block),
    }


def unpack_with_correction(corr_info: dict[str, Any] | str) -> str:
    """Unpack with correction verification."""
    if isinstance(corr_info, str):
        # assume it's a handle to correction info
        try:
            corr_data = store.resolve(corr_info)
            import json as _json
            corr_info = _json.loads(corr_data)
        except Exception:
            raise TransportError("cannot parse correction info from handle")
    if not isinstance(corr_info, dict):
        raise TransportError("corr_info must be dict or handle")
    if 'handle' not in corr_info:
        raise TransportError("missing 'handle' in corr_info")
    h = corr_info['handle']
    content = store.resolve(h)
    block = ect.ect_encode(content.encode('utf-8'))
    if not ect.ect_verify(block):
        raise TransportError("verification failed")
    return content
