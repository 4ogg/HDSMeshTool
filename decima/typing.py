from __future__ import annotations

from typing import Protocol


class ByteReaderProtocol(Protocol):
    def uint32(self, f): ...  # pragma: no cover - protocol definition only
