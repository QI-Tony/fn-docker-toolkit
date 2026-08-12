from dataclasses import dataclass
import os
from pathlib import Path


def _parse_allowed_roots(value: str) -> tuple[Path, ...]:
    roots: list[Path] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        path = Path(item)
        if not path.is_absolute():
            raise ValueError(f"ALLOWED_ROOTS 中必须使用绝对路径：{item}")
        roots.append(path.resolve(strict=False))
    if not roots:
        raise ValueError("ALLOWED_ROOTS 至少需要包含一个绝对路径")
    return tuple(roots)


@dataclass(frozen=True)
class Settings:
    allowed_roots: tuple[Path, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
        default_root = str(Path.cwd()) if os.name == "nt" else "/mnt"
        return cls(_parse_allowed_roots(os.getenv("ALLOWED_ROOTS", default_root)))
