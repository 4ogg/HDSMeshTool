"""Death Stranding-specific stream parsing helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple
from uuid import UUID

from .typing import ByteReaderProtocol


@dataclass
class StreamDescriptor:
    """Metadata extracted from a single Death Stranding vertex stream."""

    header: Tuple[int, ...]
    chunk_guid: UUID
    tail: Tuple[int, ...]


@dataclass
class VertexStreamSet:
    """Structured representation of a ``VertexStreamSet`` block."""

    vertex_count: int
    stream_count: int
    header_tail: Tuple[int, int]
    streams: List[StreamDescriptor]
    trailing: bytes

    @classmethod
    def _read_guid(cls, words: Sequence[int]) -> UUID:
        return UUID(bytes_le=b"".join(word.to_bytes(4, "little") for word in words))

    @classmethod
    def parse(cls, reader: ByteReaderProtocol, f, *, block_end: int) -> "VertexStreamSet":
        """Parse a Death Stranding ``VertexStreamSet``.

        Parameters
        ----------
        reader:
            Adapter providing ``uint32`` for little-endian parsing.
        f:
            Binary file object currently positioned at the start of the block
            payload (just after the GUID written by :class:`DataBlock`).
        block_end:
            Absolute file offset marking the end of the block so the parser can
            capture any trailing padding bytes without depending on the caller.
        """

        vertex_count = reader.uint32(f)
        stream_count = reader.uint32(f)
        field2 = reader.uint32(f)
        field3 = reader.uint32(f)

        streams: List[StreamDescriptor] = []
        for index in range(stream_count):
            header_length = 6 if index == 0 else 4
            header = tuple(reader.uint32(f) for _ in range(header_length))
            guid_words = tuple(reader.uint32(f) for _ in range(4))
            chunk_guid = cls._read_guid(guid_words)
            tail: Tuple[int, ...]
            if index == 0:
                tail = (reader.uint32(f), reader.uint32(f))
            else:
                tail = ()
            streams.append(StreamDescriptor(header=header, chunk_guid=chunk_guid, tail=tail))

        remaining = max(block_end - f.tell(), 0)
        trailing = f.read(remaining) if remaining else b""

        return cls(
            vertex_count=vertex_count,
            stream_count=stream_count,
            header_tail=(field2, field3),
            streams=streams,
            trailing=trailing,
        )
