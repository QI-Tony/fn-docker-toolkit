import hashlib
from pathlib import Path


HASH_CHUNK_SIZE = 2 * 1024 * 1024


def md5_file(path: Path, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """Calculate an MD5 using bounded-memory streaming reads."""
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()

