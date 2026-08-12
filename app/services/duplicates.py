from collections import defaultdict
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
from app.utils.hashing import md5_file


@dataclass(frozen=True)
class DuplicateFile:
    path: Path
    size: int
    md5: str


@dataclass
class DuplicateGroup:
    size: int
    md5: str
    files: list[DuplicateFile]


@dataclass
class DuplicateScan:
    root: Path
    scanned_files: int = 0
    groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duplicate_files(self) -> int:
        return sum(len(group.files) - 1 for group in self.groups)

    @property
    def reclaimable_bytes(self) -> int:
        return sum(group.size * (len(group.files) - 1) for group in self.groups)


@dataclass
class DuplicateDeletionResult:
    deleted: list[Path] = field(default_factory=list)
    reclaimed_bytes: int = 0
    errors: list[str] = field(default_factory=list)


def duplicate_group_id(group: DuplicateGroup) -> str:
    return f"{group.size}:{group.md5}"


def _collect_files(directory: Path, scan: DuplicateScan, by_size: dict[int, list[Path]]) -> None:
    try:
        with os.scandir(directory) as iterator:
            entries = list(iterator)
    except OSError as exc:
        scan.errors.append(describe_os_error(directory, exc))
        return

    for entry in entries:
        path = Path(entry.path)
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                _collect_files(path, scan, by_size)
            elif entry.is_file(follow_symlinks=False):
                size = entry.stat(follow_symlinks=False).st_size
                by_size[size].append(path)
                scan.scanned_files += 1
        except OSError as exc:
            scan.errors.append(describe_os_error(path, exc))


def scan_duplicate_files(user_path: str, allowed_roots: Iterable[Path]) -> DuplicateScan:
    root = validate_directory(user_path, allowed_roots)
    scan = DuplicateScan(root=root)
    by_size: dict[int, list[Path]] = defaultdict(list)
    _collect_files(root, scan, by_size)

    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = defaultdict(list)
        for path in paths:
            try:
                by_hash[md5_file(path)].append(path)
            except OSError as exc:
                scan.errors.append(describe_os_error(path, exc))
        for digest, matching_paths in by_hash.items():
            if len(matching_paths) > 1:
                files = [DuplicateFile(path, size, digest) for path in sorted(matching_paths)]
                scan.groups.append(DuplicateGroup(size, digest, files))

    scan.groups.sort(key=lambda group: (-group.size, str(group.files[0].path)))
    return scan


def delete_duplicate_files(
    scan: DuplicateScan,
    keep_by_group: dict[str, str],
    allowed_roots: Iterable[Path],
) -> DuplicateDeletionResult:
    result = DuplicateDeletionResult()

    for group in scan.groups:
        group_id = duplicate_group_id(group)
        selected = keep_by_group.get(group_id)
        member_paths = {str(file.path): file for file in group.files}
        if selected not in member_paths:
            result.errors.append(f"重复组 {group_id} 未选择有效的保留文件，已跳过")
            continue

        validated: list[Path] = []
        validation_error: str | None = None
        for file in group.files:
            try:
                safe_path = ensure_safe_child(file.path, scan.root, allowed_roots)
                stat = safe_path.stat()
                if not safe_path.is_file() or stat.st_size != file.size:
                    raise ValueError("文件大小已发生变化")
                if md5_file(safe_path) != file.md5:
                    raise ValueError("文件内容已发生变化")
                validated.append(safe_path)
            except (OSError, ValueError, PathValidationError) as exc:
                validation_error = f"{file.path}: {exc}"
                break

        if validation_error:
            result.errors.append(f"重复组 {group.md5} 校验失败，整组未删除：{validation_error}")
            continue

        for path in validated:
            if str(path) == selected:
                continue
            try:
                path.unlink()
                result.deleted.append(path)
                result.reclaimed_bytes += group.size
            except OSError as exc:
                result.errors.append(describe_os_error(path, exc))
    return result
