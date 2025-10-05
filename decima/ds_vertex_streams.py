"""Death Stranding-specific stream parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .typing import ByteReaderProtocol


@dataclass
class StreamDescriptor:
    raw_fields: List[int]
    guid_words: Tuple[int, int, int, int]
    trailing_bytes: bytes

    def guid_bytes_le(self) -> bytes:
        return b"".join(word.to_bytes(4, "little") for word in self.guid_words)


@dataclass
class VertexStreamSet:
    vertex_count: int
    stream_count: int
    header_tail: Tuple[int, int]
    raw_values: List[int]
    streams: List[StreamDescriptor]

    @classmethod
    def parse(cls, reader: ByteReaderProtocol, f) -> "VertexStreamSet":
        vertex_count = reader.uint32(f)
        stream_count = reader.uint32(f)
        field2 = reader.uint32(f)
        field3 = reader.uint32(f)
        raw_values: List[int] = []
        for _ in range(16):
            raw_values.append(reader.uint32(f))
        streams: List[StreamDescriptor] = []
        for _ in range(stream_count):
            guid_words = (
                reader.uint32(f),
                reader.uint32(f),
                reader.uint32(f),
                reader.uint32(f),
            )
            streams.append(StreamDescriptor(raw_fields=[], guid_words=guid_words, trailing_bytes=b""))
        return cls(
            vertex_count=vertex_count,
            stream_count=stream_count,
            header_tail=(field2, field3),
            raw_values=raw_values,
            streams=streams,
        )
