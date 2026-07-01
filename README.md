# Enum Arrays — A Zarr Convention

A [Zarr Convention][spec] for storing enum (a.k.a. dictionary-encoded / factor /
categorical) arrays: arrays (at least one) of integer **codes** that index into a smaller
1-D array of distinct **values**. This is inspired by the on-disk layout that
[AnnData][anndata-cat] uses for its categorical arrays, re-expressed using the
[Zarr Conventions][spec] discovery mechanism instead of AnnData's bespoke
`encoding-type` / `encoding-version` attributes.

- **Convention name:** `enum:`
- **UUID:** `c906c423-56ed-413c-9943-7b2ff52d18f2`
- **Schema:** [`schema.json`](./schema.json)
- **Applies to:** Zarr **groups** (`node_type: "group"`)
- **Zarr format:** 3 (the `zarr_conventions` attribute is a Zarr v3 mechanism)

## Convention Maturity

This is at maturity 0 - at the current stage, it is simply to gather feedback.
It will be published once it has reached some degree of acceptance/stability.

## Why a convention?

An enum array compresses an array drawn from a small set of repeated values by
storing each value once in `values` and storing a compact integer `codes` array
that points into it. The grouping/array layout alone does not tell a reader
"these two child arrays form an enum" — that meaning has to be attached as
metadata.

AnnData attaches it with the proprietary keys `encoding-type: "categorical"` and
`encoding-version: "0.2.0"`. This convention instead uses the standard
`zarr_conventions` attribute so that any convention-aware reader can discover the
enum by its `uuid` / `schema_url`, while low-level Zarr implementations
that don't understand the convention can still read the underlying arrays and
safely ignore the metadata.

The alternative to a two-array layout is either a per-chunk encoding, [as is done in parquet][], using arrow, which means that the full encoding can only be known by scanning all chunks.
Polars, as we are proposing, uses a custom column-level (for us, array-level) encoding [which has lead to problems][], seemingly due to its confusion with categorical types.
It does, however, circumvent the penalty of storing an encoding of the codes per-chunk, as is done for dictionary-encoding in parquet based on the arrow type.

We hope that this spec can thus provide this advantage for zarr users without confusion, especially in light of [potential future arrow compatibility][], and with the advantage of interpretability i.e., knowing all of the encodings without scanning all chunks.

[as is done in parquet]: https://parquet.apache.org/docs/file-format/data-pages/encodings/#DICTIONARY
[potential future arrow compatibility]: https://github.com/zarr-developers/zarr-extensions/pull/41
[which can lead to problems]: https://github.com/pola-rs/polars/issues/20089

## Layout

A conforming node is a Zarr group containing at least two child arrays:

```
my_enum/                   # group, carries the convention metadata and the codes array names
├── codes_1                # array, signed integer, any shape, name is marked in zarr.json `enum:codes`
├── codes_2                # array, signed integer, any shape, name is marked in zarr.json `enum:codes`
├── ...                    # more codes arrays if needed, signed integer, any shape
└── values                 # array, the distinct values, shape (K,)
```

| Member   | Kind  | Requirement                                                                                            |
| -------- | ----- | ------------------------------------------------------------------------------------------------------ |
| `codes_X`  | array | **Required.** A **signed** or **unsigned** integer dtype (`{u}int8`/`{u}int16`/`{u}int32`/`{u}int64`). Any shape. Can be any name as long as it is stored in the group `zarr.json`  correctly.  More than one of these codes arrays is allowed although there must be at least one.              |
| `values` | array | **Required.** Any Zarr dtype. 1-D, length `K`. Holds the `K` distinct values.                           |

The child encoding array **name is fixed** as `values` while the keys of the codes arrays are stored explicitly in `enum:codes`.

### Semantics

- A code `c` in a codes array denotes the logical value `values[c]`. For a 1-D codes `codes`,
  element `i` of the logical enum equals `values[codes[i]]`; for higher-rank
  `codes`, the same applies element-wise at each position.
- Each code is a zero-based index into `values`, so valid values are `0 .. K-1`.
- The sentinel code **`-1` denotes a missing value** (no value). If the type of the codes is unsigned, there are no missing values.
- No code other than `-1` may be negative if the type is signed, and no code may be `>= K`.
- Order of appearance in `values` is meaningful only when `ordered` is
  `true` (see below); it otherwise still defines the code↔value mapping but
  carries no ordering semantics.

## Convention attributes

The group's `attributes` MUST contain a `zarr_conventions` entry (per the
[spec][spec]) identifying this convention, plus the namespaced property below.

| Attribute      | Type    | Req. | Meaning                                                                                                    |
| -------------- | ------- | ---- | ---------------------------------------------------------------------------------------------------------- |
| `enum:ordered` | boolean | yes  | Whether the values have a meaningful order (`values[0] < values[1] < ...`). `false` means unordered.       |

Properties are namespaced with the `enum:` prefix to avoid collisions
with other conventions present on the same node, as recommended by the spec.

### Minimal `zarr.json` (group)

```json
{
    "zarr_format": 3,
    "node_type": "group",
    "attributes": {
        "zarr_conventions": [
            {
                "uuid": "c906c423-56ed-413c-9943-7b2ff52d18f2",
                "schema_url": "https://raw.githubusercontent.com/DOES_NOT_EXIST/zarr-convention-categorical/refs/tags/v1/schema.json",
                "spec_url": "https://github.com/DOES_NOT_EXIST/zarr-convention-categorical/blob/v1/README.md",
                "name": "enum:",
                "description": "Dictionary-encoded enum array: integer codes indexing into a values array."
            }
        ],
        "enum:ordered": false,
        "enum:codes": ["codes"]
    }
}
```

> The `schema_url` / `spec_url` above point at a `v1` tag of a yet-to-be-named-organization-owned
> repository as a worked default. This will be udpated when we publish this
> convention for the first time; per the spec, `uuid` is the stable identifier and the URLs are
> resolution hints.

## Reading an enum

A convention-aware reader:

1. Reads the group's `attributes.zarr_conventions` array and matches an entry by
   `uuid == "c906c423-56ed-413c-9943-7b2ff52d18f2"` (falling back to
   `schema_url`, then `spec_url`, per the spec's identity precedence).
2. Opens each child array at `enum:codes` and the array named `values`.
3. Either reconstructs the logical value at each code position as `values[code]`,
   mapping `code == -1` to the language's missing/null value or uses a data structure like
   `pandas.Categorical` to handle the arrays (for example, a code array and `values`).
4. Treats `values` as ordered iff `enum:ordered` is `true`.

A reader that does **not** know this convention still sees an ordinary group with
two or more readable integer/value arrays and ignores the `zarr_conventions` metadata —
the convention is **safely ignorable**.

## Versioning

This is **v1**. Backwards-incompatible changes will bump the major version and
the `v1` segment of `schema_url`. The `uuid` is permanent and does not change
across versions. See the [spec's versioning guidance][spec].

## Relationship to AnnData

| AnnData                          | This convention                                            |
| -------------------------------- | ---------------------------------------------------------- |
| `encoding-type: "categorical"`   | `zarr_conventions[].uuid == c906c423-...`                  |
| `encoding-version: "0.2.0"`      | the convention version (`v1`) via `schema_url` tag         |
| `ordered: <bool>`                | `enum:ordered: <bool>`                                     |
| child arrays `codes`/`categories`| child arrays, multiple potential `enum:codes` and one `values`                              |

The byte-level layout of the codes and the distinct-values array is identical to
AnnData's (AnnData names the latter `categories`; this convention names it
`values`), so existing data can be made conformant by renaming the
`categories` array to `values` and rewriting the group attributes to include `codes` in the `enum:codes` json field.

## Examples

See [`examples/`](./examples):

- [`examples/ordered/`](./examples/ordered) — an ordered enum with a
  missing value, as a full set of Zarr v3 `zarr.json` documents.
- [`examples/generate.py`](./examples/generate.py) — builds a real Zarr store
  with this convention and reads it back.

## License

BSD-3-Clause. See [LICENSE](./LICENSE).

[spec]: https://github.com/zarr-conventions/zarr-conventions-spec
[anndata-cat]: https://anndata.scverse.org/en/stable/fileformat-prose.html#categorical-arrays
