"""Generate a stream layout helper for Death Stranding meshes.

The existing Blender importer expects Horizon Zero Dawn style per-primitive
streams.  Death Stranding stores the same data in shared mesh-wide buffers,
with the slicing instructions described in companion `.dmf` exports produced
by Decima Workshop.  This utility stitches the `.core` metadata together with
the `.dmf` buffer description so that we can feed structured stream
information into future importer work.

It is intentionally conservative: the tool only relies on information that is
already present in the provided reverse-engineering assets and refrains from
guessing at yet-undocumented chunk-table structures.  The resulting JSON maps
each vertex stream set GUID to the buffer view offsets, strides, and semantic
layout reported by Decima Workshop, keyed by the rendering primitive order
found inside the `.core` file.
"""
from __future__ import annotations

import argparse
import json
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping


VERTEX_STREAM_SET_ID = 0x3AC29A123FAABAB4
PRIMITIVE_RESOURCE_ID = 0xEE49D93DA4C1F4B8


@dataclass
class Block:
    block_id: int
    guid: uuid.UUID
    payload: bytes


def iter_blocks(blob: bytes) -> Iterator[Block]:
    """Yield ``Block`` entries from a Decima ``.core`` blob."""

    offset = 0
    view = memoryview(blob)
    while offset + 28 <= len(blob):
        (block_id,) = struct.unpack_from("<Q", view, offset)
        offset += 8
        (size,) = struct.unpack_from("<i", view, offset)
        offset += 4
        guid = uuid.UUID(bytes_le=bytes(view[offset : offset + 16]))
        offset += 16
        payload = bytes(view[offset : offset + size - 16])
        offset += size - 16
        yield Block(block_id=block_id, guid=guid, payload=payload)


@dataclass
class VertexStreamSet:
    guid: uuid.UUID
    vertex_count: int


def parse_vertex_stream_set(block: Block) -> VertexStreamSet:
    (vertex_count,) = struct.unpack_from("<I", block.payload, 0)
    return VertexStreamSet(guid=block.guid, vertex_count=vertex_count)


@dataclass
class PrimitiveReference:
    guid: uuid.UUID
    vertex_ref: uuid.UUID
    index_ref: uuid.UUID


def parse_primitive_reference(block: Block) -> PrimitiveReference:
    data = memoryview(block.payload)
    offset = 4  # skip flags
    vertex_type = data[offset]
    offset += 1
    vertex_guid = uuid.UUID(bytes_le=bytes(data[offset : offset + 16]))
    offset += 16
    index_type = data[offset]
    offset += 1
    index_guid = uuid.UUID(bytes_le=bytes(data[offset : offset + 16]))
    _ = vertex_type, index_type  # type markers retained for potential validation
    return PrimitiveReference(guid=block.guid, vertex_ref=vertex_guid, index_ref=index_guid)


def load_vertex_sets(core_blob: bytes) -> Dict[uuid.UUID, VertexStreamSet]:
    sets: Dict[uuid.UUID, VertexStreamSet] = {}
    for block in iter_blocks(core_blob):
        if block.block_id == VERTEX_STREAM_SET_ID:
            sets[block.guid] = parse_vertex_stream_set(block)
    return sets


def load_primitives(core_blob: bytes) -> List[PrimitiveReference]:
    refs: List[PrimitiveReference] = []
    for block in iter_blocks(core_blob):
        if block.block_id == PRIMITIVE_RESOURCE_ID:
            refs.append(parse_primitive_reference(block))
    return refs


def group_attributes_by_view(attributes: Mapping[str, Mapping[str, object]]) -> Dict[int, List[Mapping[str, object]]]:
    grouped: Dict[int, List[Mapping[str, object]]] = {}
    for semantic, payload in attributes.items():
        if "bufferViewId" not in payload:
            continue
        view_id = int(payload["bufferViewId"])
        enriched = dict(payload)
        enriched["semantic"] = semantic
        grouped.setdefault(view_id, []).append(enriched)
    return grouped


def build_mapping(
    vertex_sets: Mapping[uuid.UUID, VertexStreamSet],
    primitives: Iterable[PrimitiveReference],
    dmf: Mapping[str, object],
) -> Dict[str, object]:
    """Match ``VertexStreamSet`` GUIDs with ``.dmf`` buffer views."""

    instance_primitives = list(dmf.get("instances", [{}])[0].get("mesh", {}).get("primitives", []))
    buffer_views: List[Mapping[str, int]] = dmf.get("bufferViews", [])

    primitive_list = list(primitives)
    limit = min(len(primitive_list), len(instance_primitives))
    if limit == 0:
        raise RuntimeError("No primitives found in either the .core or .dmf assets")
    if len(primitive_list) != len(instance_primitives):
        print(
            "[warn] primitive count mismatch between .core and .dmf exports; "
            f"truncating to {limit} entries"
        )
    result: MutableMapping[str, object] = {}

    for prim_ref, dmf_prim in zip(primitive_list[:limit], instance_primitives[:limit]):
        vertex_set = vertex_sets.get(prim_ref.vertex_ref)
        if vertex_set is None:
            raise KeyError(f"Vertex stream set {prim_ref.vertex_ref} not found in .core")

        grouped = group_attributes_by_view(dmf_prim.get("vertexAttributes", {}))
        streams: List[Mapping[str, object]] = []

        for view_id, attributes in grouped.items():
            try:
                buffer_view = buffer_views[view_id]
            except IndexError as exc:  # pragma: no cover - defensive guard
                raise IndexError(f"bufferViewId {view_id} missing from .dmf bufferViews") from exc

            stream_entry = {
                "bufferViewId": view_id,
                "offset": buffer_view.get("offset", 0),
                "length": buffer_view.get("size", 0),
                "attributes": attributes,
            }
            if attributes:
                stream_entry["stride"] = attributes[0].get("stride")
            streams.append(stream_entry)

        result[str(prim_ref.vertex_ref)] = {
            "vertexCount": vertex_set.vertex_count,
            "primitiveGuid": str(prim_ref.guid),
            "streams": streams,
            "index": {
                "count": dmf_prim.get("indexCount"),
                "bufferViewId": dmf_prim.get("indexBufferViewId"),
                "size": dmf_prim.get("indexSize"),
            },
        }

    return dict(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path, help="Death Stranding .core file")
    parser.add_argument("dmf", type=Path, help="Companion Decima Workshop .dmf export")
    parser.add_argument("--output", type=Path, help="Destination JSON path (defaults to <core>.streams.json)")
    args = parser.parse_args()

    core_blob = args.core.read_bytes()
    vertex_sets = load_vertex_sets(core_blob)
    primitive_refs = load_primitives(core_blob)
    dmf_payload = json.loads(args.dmf.read_text())

    mapping = build_mapping(vertex_sets, primitive_refs, dmf_payload)
    output_path = args.output or args.core.with_suffix(args.core.suffix + ".streams.json")
    output_path.write_text(json.dumps(mapping, indent=2, sort_keys=True))
    print(f"Wrote stream mapping for {len(mapping)} primitives to {output_path}")


if __name__ == "__main__":
    main()

