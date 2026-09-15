"""Snowflake IDs for chat timeline ordering (channel + id DESC)."""

from __future__ import annotations

import threading
import time

# Custom epoch: 2024-01-01 UTC
_EPOCH_MS = 1_704_067_200_000
_WORKER_ID = 1
_lock = threading.Lock()
_last_ms = 0
_seq = 0


def next_snowflake() -> int:
    global _last_ms, _seq
    with _lock:
        now = int(time.time() * 1000)
        if now == _last_ms:
            _seq = (_seq + 1) & 0xFFF
            if _seq == 0:
                while now <= _last_ms:
                    now = int(time.time() * 1000)
        else:
            _seq = 0
        _last_ms = now
        return ((now - _EPOCH_MS) << 22) | ((_WORKER_ID & 0x3FF) << 12) | _seq
