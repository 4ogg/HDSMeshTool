# Death Stranding Format Notes

## Vertex stream layout in `mesh_test.dmf`
- Primitive 0 uses three vertex buffer views with matching strides for position/weights (`stride = 28`), normals/tangents (`stride = 28`), and colour/UV (`stride = 8`).
- Primitive 1 reuses the same pattern with different offsets.  All buffer views reference a single buffer (`ds/...file.stream`) with distinct offsets and sizes, meaning the mesh data is stored once per mesh and partitioned for each primitive.【F:DSfiles/mesh_test.dmf†L4623-L4662】【F:DSfiles/mesh_test.dmf†L4663-L4691】

## Block identifiers discovered in `mesh_test.core`
- Rendering primitives use block ID `0xEE49D93DA4C1F4B8` and reference vertex streams via GUIDs such as `71d9d23d-5e9f-b930-ab89-ef0525098768` and index streams via GUIDs like `4a8b7d12-47f7-8a3b-9d47-290596427690`.【F:tools/analyze_ds_core.py†L200-L229】【719378†L28-L34】
- Vertex stream sets share block ID `0x3AC29A123FAABAB4` and expose three chunked streams per mesh (positions, normals/tangents, UV/colour).  The raw integer payload shows per-stream metadata followed by GUID links back to chunk tables, highlighting the difference from HZD's per-primitive streams.【F:tools/analyze_ds_core.py†L89-L157】【e1d068†L33-L43】
- Chunk tables live in blocks with ID `0x0B0D03C7E087F38E`, confirming that Death Stranding groups stream data per mesh and references shared chunks across primitives/LODs.【F:tools/analyze_ds_core.py†L40-L78】【719378†L22-L26】

## Observations
- Death Stranding stores vertex data per mesh with shared chunk tables, while Horizon Zero Dawn stores separate vertex streams per primitive.  The `.dmf` buffer view definitions map directly onto the chunked layout exposed by the new block IDs.
- To support Death Stranding we will need new parsing code that can interpret the `VertexStreamSet` blocks, resolve their chunk tables, and slice the shared buffer into primitive-specific ranges before handing data to Blender.

## Tooling
- `tools/dump_ds_stream_map.py` links `VertexStreamSet` GUIDs from a `.core` file with the buffer view layout exported by Decima Workshop. The script emits a JSON document per mesh that records vertex counts, buffer view offsets/lengths, and attribute semantics for each shared stream; this remains useful for analysis, but the importer now expects a `<core>.chunk_tables.json` breakdown that lists per-stream offsets and sizes derived from the Death Stranding chunk tables.【F:tools/dump_ds_stream_map.py†L1-L194】
