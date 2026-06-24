"""Write and read back a simple enum array using the Zarr convention.

This builds a Zarr v3 group conforming to the enum convention
(uuid c906c423-56ed-413c-9943-7b2ff52d18f2) *without* using AnnData's
``encoding-type`` / ``encoding-version`` attributes — discovery happens purely
through the standard ``zarr_conventions`` attribute.

Requires ``zarr>=3``. Run with::

    python examples/generate.py
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import numpy as np
import zarr

CONVENTION_UUID = "c906c423-56ed-413c-9943-7b2ff52d18f2"

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())

CONVENTION_METADATA = {
    "uuid": CONVENTION_UUID,
    "schema_url": "https://raw.githubusercontent.com/TBD/zarr-convention-categorical/refs/tags/v1/schema.json",
    "spec_url": "https://github.com/TBD/zarr-convention-categorical/blob/v1/README.md",
    "name": "enum:",
    "description": "Dictionary-encoded enum array: integer codes indexing into a values array.",
}


def validate_attrs(grp: zarr.Group) -> None:
    """Validate a group's attributes against ``schema.json``.

    Raises ``jsonschema.ValidationError`` if the attributes do not conform.
    """
    jsonschema.validate(instance=dict(grp.attrs), schema=SCHEMA)


def write_enum(
    parent: zarr.Group,
    name: str,
    codes: np.ndarray,
    values: np.ndarray,
    *,
    ordered: bool,
) -> zarr.Group:
    """Create ``name`` under ``parent`` as a conforming enum group."""
    if codes.dtype.kind != "i":
        raise ValueError("codes must be a signed integer array (-1 means missing)")
    if values.ndim != 1:
        raise ValueError("values must be a 1-D array")
    valid = codes[codes != -1]
    if valid.size and (valid.min() < 0 or valid.max() >= len(values)):
        raise ValueError("every non-(-1) code must index into values")

    grp = parent.create_group(name)
    grp.attrs["zarr_conventions"] = [CONVENTION_METADATA]
    grp.attrs["enum:ordered"] = bool(ordered)
    grp.attrs["enum:codes"] = ["codes"]

    grp.create_array("codes", shape=codes.shape, dtype=codes.dtype)[:] = codes
    vals = grp.create_array("values", shape=values.shape, dtype=values.dtype)
    vals[:] = values

    validate_attrs(grp)
    return grp


def is_enum(grp: zarr.Group) -> bool:
    """Discover the convention by uuid (then schema_url, then spec_url)."""
    for cmo in grp.attrs.get("zarr_conventions", []):
        if cmo.get("uuid") == CONVENTION_UUID:
            return True
    return False


def read_enum(grp: zarr.Group) -> np.ndarray:
    """Reconstruct the logical values, mapping code -1 to None.

    Works for ``codes`` of any rank; the result is an object array of the same
    shape, with ``None`` wherever the code is ``-1``.
    """
    (codes_key,) = grp.attrs["enum:codes"]
    codes = grp[codes_key][:]
    values = grp["values"][:]
    out = np.empty(codes.shape, dtype=object)
    flat = codes.reshape(-1)
    out_flat = out.reshape(-1)
    for i, c in enumerate(flat):
        out_flat[i] = None if c == -1 else values[c]
    return out


def main() -> None:
    root = zarr.open_group(store=zarr.storage.MemoryStore(), mode="w")

    codes = np.array([0, 1, 2, -1, 1], dtype="int8")
    values = np.array(["low", "medium", "high"], dtype="T")
    write_enum(root, "quality", codes, values, ordered=True)

    grp = root["quality"]
    assert is_enum(grp), "convention not discoverable"
    validate_attrs(grp)
    assert grp.attrs["enum:ordered"] is True
    reconstructed = read_enum(grp)
    print("ordered:", grp.attrs["enum:ordered"])
    print("values: ", list(reconstructed))
    assert list(reconstructed) == ["low", "medium", "high", None, "medium"]


if __name__ == "__main__":
    main()
