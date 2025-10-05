"""Utility to inspect Death Stranding .core files.

The Horizon Zero Dawn mesh tool expects per-primitive vertex streams.  Death
Stranding reorganises the same data into chunked streams that are shared by
multiple primitives.  This helper performs a light-weight parse of a .core file
so we can reason about the new layout without requiring Blender.
"""
from __future__ import annotations

import argparse
import dataclasses
import struct
import uuid
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Tuple

# Known block identifiers gathered from analysing mesh_test.core.  The Horizon
# Zero Dawn tool uses a different numeric set, therefore the first step towards
# supporting Death Stranding is to map the new IDs back to the conceptual
# structures that the add-on expects.
BLOCK_NAMES: Dict[int, str] = {
    0x6319028A13556F1E: "DataBufferResource?",
    0x36B88667B0A33134: "RegularSkinnedMeshResource",
    0xE2A812418ABC2172: "SkinnedMeshBoneBindings",
    0xBCE84D96052C041E: "SkinnedMeshBoneBoundingBoxes",
    0x118378C2F191097A: "RegularSkinnedMeshResourceSkinInfo",
    0xFE2843D4AAD255E7: "RenderEffectResource",
    0x0B0D03C7E087F38E: "StreamChunkTable",
    0x8EB29E71F97E460F: "CullInfo/LOD meta",
    0xEE49D93DA4C1F4B8: "RenderingPrimitiveResource",
    0x3AC29A123FAABAB4: "VertexStreamSet",
    0x5FE633B37CEDBF84: "IndexStream",
}


def _read(fmt: str, data: memoryview, offset: int) -> Tuple[Tuple[int, ...], int]:
    size = struct.calcsize(fmt)
    values = struct.unpack_from(fmt, data, offset)
    return values, offset + size


@dataclasses.dataclass
class Block:
    offset: int
    block_id: int
    size: int
    guid: uuid.UUID
    payload: bytes

    @property
    def name(self) -> str:
        return BLOCK_NAMES.get(self.block_id, f"0x{self.block_id:016X}")


def iter_blocks(blob: bytes) -> Iterator[Block]:
    offset = 0
    view = memoryview(blob)
    while offset + 28 <= len(blob):
        (block_id,), offset = _read("<Q", view, offset)
        (size,), offset = _read("<i", view, offset)
        guid_bytes = bytes(view[offset : offset + 16])
        offset += 16
        payload = bytes(view[offset : offset + size - 16])
        offset += size - 16
        yield Block(
            offset=offset - size,
            block_id=block_id,
            size=size,
            guid=uuid.UUID(bytes_le=guid_bytes),
            payload=payload,
        )


@dataclasses.dataclass
class StreamDescriptor:
    raw_fields: List[int]
    guid: uuid.UUID
    trailing: bytes

    def describe(self) -> Dict[str, object]:
        base: Dict[str, object] = {
            "raw_fields": self.raw_fields,
            "guid": str(self.guid),
        }
        if self.trailing:
            base["trailing_bytes"] = self.trailing.hex()
        return base


@dataclasses.dataclass
class VertexStreamSet:
    vertex_count: int
    stream_count: int
    header_tail: Tuple[int, int]
    streams: List[StreamDescriptor]
    raw_values: List[int]

    @classmethod
    def parse(cls, block: Block) -> "VertexStreamSet":
        payload = block.payload
        head = memoryview(payload)
        offset = 0
        (vertex_count, stream_count, field2, field3), offset = _read(
            "<IIII", head, offset
        )
        remaining = payload[offset:]
        ints = list(
            struct.unpack(
                "<" + "I" * (len(remaining) // 4), remaining[: len(remaining) // 4 * 4]
            )
        )
        tail = remaining[len(ints) * 4 :]
        guid_words = ints[-stream_count * 4 :] if stream_count else []
        raw_values = ints[: -stream_count * 4] if stream_count else ints
        streams: List[StreamDescriptor] = []
        for i in range(stream_count):
            words = guid_words[i * 4 : (i + 1) * 4]
            guid_bytes = b"".join(struct.pack("<I", value) for value in words)
            streams.append(StreamDescriptor(raw_fields=[], guid=uuid.UUID(bytes_le=guid_bytes), trailing=b""))
        if streams:
            streams[-1].trailing = tail
        vertex_set = cls(
            vertex_count=vertex_count,
            stream_count=stream_count,
            header_tail=(field2, field3),
            streams=streams,
            raw_values=raw_values,
        )
        # Attach the raw integers to the first stream descriptor for debugging
        # purposes so downstream tooling can inspect the per-stream metadata
        # without guessing at the layout yet.
        if vertex_set.streams:
            vertex_set.streams[0].raw_fields = raw_values
        return vertex_set

    def to_dict(self) -> Dict[str, object]:
        return {
            "vertex_count": self.vertex_count,
            "stream_count": self.stream_count,
            "header_tail": self.header_tail,
            "raw_values": self.raw_values,
            "streams": [stream.describe() for stream in self.streams],
        }


@dataclasses.dataclass
class IndexStream:
    index_count: int
    unknown: Tuple[int, int, int]
    guid: uuid.UUID

    @classmethod
    def parse(cls, block: Block) -> "IndexStream":
        data = memoryview(block.payload)
        offset = 0
        (index_count, field1, field2, field3), offset = _read("<IIII", data, offset)
        guid_bytes = bytes(data[offset : offset + 16])
        guid = uuid.UUID(bytes_le=guid_bytes)
        return cls(index_count=index_count, unknown=(field1, field2, field3), guid=guid)

    def to_dict(self) -> Dict[str, object]:
        return {
            "index_count": self.index_count,
            "unknown": self.unknown,
            "guid": str(self.guid),
        }


@dataclasses.dataclass
class PrimitiveSummary:
    guid: uuid.UUID
    vertex_ref: uuid.UUID
    index_ref: uuid.UUID

    @classmethod
    def parse(cls, block: Block) -> "PrimitiveSummary":
        data = memoryview(block.payload)
        offset = 4  # skip flags
        vertex_type = data[offset]
        offset += 1
        vertex_guid = uuid.UUID(bytes_le=bytes(data[offset : offset + 16]))
        offset += 16
        index_type = data[offset]
        offset += 1
        index_guid = uuid.UUID(bytes_le=bytes(data[offset : offset + 16]))
        return cls(guid=block.guid, vertex_ref=vertex_guid, index_ref=index_guid)

    def to_dict(self) -> Dict[str, str]:
        return {
            "primitive": str(self.guid),
            "vertex_ref": str(self.vertex_ref),
            "index_ref": str(self.index_ref),
        }


def summarise(path: Path) -> Dict[str, object]:
    blob = path.read_bytes()
    blocks = list(iter_blocks(blob))
    summary: Dict[str, object] = {
        "block_count": len(blocks),
        "blocks": [],
    }
    primitives: List[Dict[str, str]] = []
    vertex_sets: Dict[uuid.UUID, Dict[str, object]] = {}
    index_sets: Dict[uuid.UUID, Dict[str, object]] = {}
    for block in blocks:
        entry = {
            "offset": block.offset,
            "id": f"0x{block.block_id:016X}",
            "name": block.name,
            "size": block.size,
            "guid": str(block.guid),
        }
        if block.block_id == 0xEE49D93DA4C1F4B8:
            primitive = PrimitiveSummary.parse(block)
            entry["details"] = primitive.to_dict()
            primitives.append(primitive.to_dict())
        elif block.block_id == 0x3AC29A123FAABAB4:
            vertex = VertexStreamSet.parse(block)
            vertex_sets[block.guid] = vertex.to_dict()
            entry["details"] = vertex.to_dict()
        elif block.block_id == 0x5FE633B37CEDBF84:
            index = IndexStream.parse(block)
            index_sets[block.guid] = index.to_dict()
            entry["details"] = index.to_dict()
        summary["blocks"].append(entry)
    summary["primitives"] = primitives
    summary["vertex_sets"] = vertex_sets
    summary["index_sets"] = index_sets
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path, help="Death Stranding .core file")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit the number of blocks displayed in the textual summary",
    )
    args = parser.parse_args()
    data = summarise(args.core)
    blocks: Sequence[Dict[str, object]] = data["blocks"]
    limit = args.limit or len(blocks)
    for block in blocks[:limit]:
        print(f"{block['offset']:08x} {block['name']:>28} {block['size']:6d} {block['guid']}")
        details = block.get("details")
        if isinstance(details, dict):
            for key, value in details.items():
                print(f"    {key}: {value}")
    print(f"Total blocks: {data['block_count']}")


if __name__ == "__main__":
    main()
