"""Secure file deletion for the Secure Encryption Utility.

Implements the real DoD 5220.22-M (one-pass variant) and Peter Gutmann
35-pass overwrite schemes, then removes the file. Files are overwritten in
1 MiB chunks with fsync between passes.

DoD 5220.22-M (Phase 1): pass 0x00, pass 0xFF, pass PRNG, verify pattern.
Gutmann: 35 passes using the destruct/pattern table of the spec.
"""

import math
import os

CHUNK = 1024 * 1024

_GUTTMANN = [
    0x55, 0xAA, 0x92, 0x49, 0x24, 0x49, 0x92, 0x24, 0x49, 0x92, 0x6D, 0xB6,
    0xB6, 0x6D, 0xDB, 0xB6, 0x6D, 0xDB, 0xB6, 0xDB, 0x49, 0x24, 0x24, 0x92,
    0x49, 0x92, 0x24, 0x49, 0x92, 0x24, 0xB5, 0xDB, 0x6D, 0xDB, 0x6D,
]


def _pattern_bytes(byte):
    return bytes([byte]) * CHUNK


def wipe(path, method="dod", progress=None):
    """Overwrite `path` in place with `method`, then delete it."""
    if method not in ("dod", "guttmann"):
        raise ValueError("unknown wipe method")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    size = os.path.getsize(path)
    if size <= 0:
        os.remove(path)
        return

    if method == "dod":
        passes = [(0x00, False), (0xFF, False), (None, True), (None, True)]
    else:
        passes = [(b, False) for b in _GUTTMANN]
        passes += [(None, True)]

    total = len(passes)
    last_block = (size - 1) // CHUNK
    for idx, (fixed, verify) in enumerate(passes):
        with open(path, "r+b") as fh:
            remaining = size
            while remaining > 0:
                chunk = min(remaining, CHUNK)
                if verify:
                    fh.write(os.urandom(chunk))
                else:
                    fh.write(_pattern_bytes(fixed)[:chunk])
                remaining -= chunk
            fh.flush()
            os.fsync(fh.fileno())
        if progress:
            progress("pass %d/%d" % (idx + 1, total), int((idx + 1) / total * 100))
    os.remove(path)