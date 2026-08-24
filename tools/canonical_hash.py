from __future__ import annotations

import hashlib
from os import PathLike
from pathlib import Path


HASH_POLICY = "lf-normalized-utf8-text-else-raw-v1"


def _canonical_bytes(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    if "\x00" in text:
        return data
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(_canonical_bytes(data)).hexdigest()


def sha256_file(path: str | PathLike[str]) -> str:
    return sha256_bytes(Path(path).read_bytes())
