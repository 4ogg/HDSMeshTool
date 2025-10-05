# HZDMeshTool

Blender add-on for exploring and modifying meshes built on Guerrilla Games' Decima engine. The tool began as an importer/exporter for **Horizon Zero Dawn** and now bundles experimental research toward **Death Stranding** support, including data-mining utilities and format notes.

## Feature status

| Area | Status | Notes |
| --- | --- | --- |
| Horizon Zero Dawn skeletal meshes | ✅ Stable | Import/export of `.core`/`.stream` pairs through the Blender add-on. Original workflows remain intact. |
| Death Stranding mesh import | ⚠️ In progress | Vertex stream metadata is parsed, but chunked buffers are not yet expanded into Blender meshes. |
| Death Stranding mesh export | ❌ Blocked | Export raises a `DeathStrandingExportError` until shared stream repacking is implemented. |
| Tooling | ✅ Stable | `tools/analyze_ds_core.py` dumps block/stream metadata to aid reverse-engineering. |

## Repository layout

- `__init__.py` – Blender add-on entry point containing the Horizon toolchain plus Death Stranding guards and stream parsing hooks.
- `decima/` – Supporting modules, including Death Stranding helpers (`ds_vertex_streams.py`, `ds_export.py`) and shared typing utilities.
- `docs/death_stranding_analysis.md` – Notes captured while comparing Death Stranding assets to the legacy Horizon format.
- `tools/analyze_ds_core.py` – Standalone CLI for inspecting `.core` meshes and enumerating vertex/index references.
- `DSfiles/` – Sample Death Stranding assets used for analysis and testing.

## Installation (Blender add-on)

1. Download the repository or grab a packaged `.zip` from your preferred distribution method.
2. In Blender, open **Edit → Preferences… → Add-ons** and choose **Install…**
3. Select the `HZDMeshTool.zip` archive (or the cloned repository folder) and enable **HZD Mesh Tool**.
4. A new **HZD Mesh Tool** panel appears under **Scene Properties**.

## Working with Horizon Zero Dawn assets

The legacy workflow remains unchanged:

1. Go to **Scene Properties → HZD Mesh Tool**.
2. Either extract directly from your game install (set *Workspace Path*, *Game Path*, *Asset Path* and click **Extract**) or point the tool at already-extracted `.core` files.
3. Click **Search Data** to list the LOD objects and mesh parts found inside the mesh `.core` file.
4. Use the import icons to bring individual mesh parts (or the **Import** button for a full LOD) into Blender. Skeletons are auto-imported on demand.
5. Edit the mesh while preserving vertex group order, UV/VColor channel counts, and skeleton structure.
6. Use the export icons (or **Export** button) to overwrite the corresponding `.core`/`.stream` pair. LOD distances can also be edited and saved from the panel.

Texture extraction, material creation, and node-group helpers continue to function when the **Extract Textures** option is enabled and the workspace is configured.

## Experimental Death Stranding support

Death Stranding stores vertex data as mesh-wide stream sets with shared chunk tables. The add-on now recognises these resources and preserves their metadata during parsing, but Blender import/export is still incomplete:

- Import currently stops after recording the `VertexStreamSet` descriptors. Vertex buffers are not yet sliced per primitive, so meshes will not appear in Blender.
- Export short-circuits with a clear error because chunked stream repacking has not been written.
- The `tools/analyze_ds_core.py` utility can be used to inspect `.core` files, study block relationships, and collect GUIDs for future implementation work:
  ```bash
  python tools/analyze_ds_core.py DSfiles/mesh_test.core --limit 40
  ```

Refer to `docs/death_stranding_analysis.md` for the observed stream layout, block identifiers, and differences from Horizon Zero Dawn.

## Remaining work

- [ ] Slice Death Stranding `VertexStreamSet` buffers into `StreamData` objects so meshes can be instantiated in Blender.
- [ ] Rebuild Death Stranding chunk tables during export, packing vertex and index data per mesh before writing `.stream` files.
- [ ] Audit index buffer handling to confirm whether Death Stranding also shares chunked indices across primitives.
- [ ] Extend automated tests/dev workflows to cover Death Stranding parsing once geometry import succeeds.
- [ ] Document any additional Decima titles or format variations encountered during development.

## Contributing

Pull requests and research findings are welcome. Please include reproduction steps or command examples when reporting Death Stranding issues so the community can iterate on the format support.

