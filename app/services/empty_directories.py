from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Iterable

from app.utils.filesystem import (
    PathValidationError,
    describe_os_error,
    ensure_safe_child,
    validate_directory,
)


@dataclass
class EmptyDirectoryScan:
    root: Path
    directories: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class DeletionResult:
    deleted: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def scan_empty_directories(user_path: str, allowed_roots: Iterable[Path]) -> EmptyDirectoryScan:
    root = validate_directory(user_path, allowed_roots)
    result = EmptyDirectoryScan(root=root)

    def visit(directory: Path, is_root: bool = False) -> bool:
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError as exc:
            result.errors.append(describe_os_error(directory, exc))
            return False

        logically_empty = True
        for entry in entries:
            try:
                if entry.is_symlink():
                    logically_empty = False
                elif entry.is_dir(follow_symlinks=False):
                    if not visit(Path(entry.path)):
                        logically_empty = False
                else:
                    logically_empty = False
            except OSError as exc:
                result.errors.append(describe_os_error(Path(entry.path), exc))
                logically_empty = False

        if logically_empty and not is_root:
            result.directories.append(directory)
        return logically_empty

    visit(root, is_root=True)
    return result


def delete_empty_directories(
    scan: EmptyDirectoryScan, allowed_roots: Iterable[Path]
) -> DeletionResult:
    result = DeletionResult()
    # Scan order is already deepest-first; sorting also protects callers that construct scans.
    candidates = sorted(scan.directories, key=lambda item: len(item.parts), reverse=True)
    for directory in candidates:
        try:
            safe_path = ensure_safe_child(directory, scan.root, allowed_roots)
            safe_path.rmdir()
            result.deleted.append(safe_path)
        except (OSError, PathValidationError) as exc:
            result.errors.append(f"{directory}: {exc}")
    return result

