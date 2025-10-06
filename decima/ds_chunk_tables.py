"""Helpers for consuming Death Stranding chunk-table breakdowns."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, MutableMapping, Optional, Sequence
from uuid import UUID


@dataclass
class Chunk:
    primitive_guid: UUID
    offset: int
    length: int
    vertex_count: int


@dataclass
class StreamLayout:
    role: str
    stride: int
    chunks: Sequence[Chunk]

    def chunk_for(self, primitive_guid: UUID) -> Optional[Chunk]:
        for chunk in self.chunks:
            if chunk.primitive_guid == primitive_guid:
                return chunk
        return None


@dataclass
class VertexSetLayout:
    vertex_count: int
    streams: Mapping[str, StreamLayout]


class ChunkTableStore:
    """Caches chunk table JSON breakdowns per mesh."""

    def __init__(self) -> None:
        self._cache: MutableMapping[Path, Mapping[UUID, VertexSetLayout]] = {}

    def load(self, core_path: Path) -> Mapping[UUID, VertexSetLayout]:
        if core_path in self._cache:
            return self._cache[core_path]

        candidate = core_path.with_suffix(".chunk_tables.json")
        if not candidate.exists():
            raise FileNotFoundError(candidate)

        payload = json.loads(candidate.read_text())
        vertex_sets: Dict[UUID, VertexSetLayout] = {}

        for guid_hex, entry in payload.get("vertexSets", {}).items():
            streams: Dict[str, StreamLayout] = {}
            for role, stream_data in entry.get("streams", {}).items():
                chunks = [
                    Chunk(
                        primitive_guid=UUID(chunk["primitiveGuid"]),
                        offset=int(chunk["offset"]),
                        length=int(chunk["length"]),
                        vertex_count=int(
                            chunk.get("vertexCount", entry.get("vertexCount", 0))
                        ),
                    )
                    for chunk in stream_data.get("chunks", [])
                ]
                streams[role] = StreamLayout(
                    role=role,
                    stride=int(stream_data.get("stride", 0)),
                    chunks=chunks,
                )
            vertex_sets[UUID(guid_hex)] = VertexSetLayout(
                vertex_count=int(entry.get("vertexCount", 0)),
                streams=streams,
            )

        self._cache[core_path] = vertex_sets
        return vertex_sets


_STORE = ChunkTableStore()


def load_layout(core_path: Path) -> Mapping[UUID, VertexSetLayout]:
    """Load the chunk-table layout for ``core_path``."""

    return _STORE.load(core_path)
