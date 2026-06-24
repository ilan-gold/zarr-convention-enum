# Changelog

## v1 — unreleased

Initial version of the enum array Zarr convention.

- UUID `c906c423-56ed-413c-9943-7b2ff52d18f2`.
- Group with child arrays `codes` (signed integer, any shape, `-1` = missing)
  and `values` (the 1-D array of distinct values).
- `enum:ordered` boolean attribute.
- Discovery via the standard `zarr_conventions` attribute rather than AnnData's
  `encoding-type` / `encoding-version`.
