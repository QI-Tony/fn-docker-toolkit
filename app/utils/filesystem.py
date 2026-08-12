import os
from pathlib import Path
from typing import Iterable


class PathValidationError(ValueError):
    """Raised when a user-provided path is missing, invalid, or out of scope."""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_symlink_component(path: Path, stop_at: Path | None = None) -> bool:
    """Check a lexical path without resolving any of its components."""
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent or current == stop_at:
            return False
        current = current.parent


def validate_directory(user_path: str, allowed_roots: Iterable[Path]) -> Path:
    """Validate and resolve an existing directory against the configured roots."""
    if not user_path or not user_path.strip():
        raise PathValidationError("请输入要扫描的目录")
    if "\x00" in user_path:
        raise PathValidationError("路径包含无效字符")

    raw = Path(user_path.strip())
    if not raw.is_absolute():
        raise PathValidationError("请输入绝对路径")
    if ".." in raw.parts:
        raise PathValidationError("路径中不允许包含 '..'")
    if _has_symlink_component(raw):
        raise PathValidationError(f"扫描路径不能包含 symbolic link：{raw}")

    try:
        resolved = raw.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathValidationError(f"路径不存在：{raw}") from exc
    except (OSError, RuntimeError) as exc:
        raise PathValidationError(f"无法解析路径：{raw}（{exc}）") from exc

    if not resolved.is_dir():
        raise PathValidationError(f"路径不是目录：{raw}")

    resolved_roots = tuple(Path(root).resolve(strict=False) for root in allowed_roots)
    if not any(_is_relative_to(resolved, root) for root in resolved_roots):
        allowed = ", ".join(str(root) for root in resolved_roots)
        raise PathValidationError(f"路径不在允许范围内。允许的根目录：{allowed}")
    return resolved


def ensure_safe_child(path: Path, scan_root: Path, allowed_roots: Iterable[Path]) -> Path:
    """Revalidate a discovered item immediately before a destructive operation."""
    if path == scan_root:
        raise PathValidationError("禁止删除扫描根目录")
    try:
        path.relative_to(scan_root)
    except ValueError as exc:
        raise PathValidationError(f"路径超出扫描目录：{path}") from exc
    if _has_symlink_component(path, stop_at=scan_root):
        raise PathValidationError(f"拒绝操作 symbolic link：{path}")
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathValidationError(f"路径已不存在：{path}") from exc

    roots = tuple(Path(root).resolve(strict=False) for root in allowed_roots)
    if not _is_relative_to(resolved, scan_root) or not any(
        _is_relative_to(resolved, root) for root in roots
    ):
        raise PathValidationError(f"路径超出允许范围：{path}")
    return resolved


def describe_os_error(path: Path, exc: OSError) -> str:
    detail = exc.strerror or str(exc)
    return f"{path}: {detail}"


def is_regular_file_without_following_symlinks(entry: os.DirEntry[str]) -> bool:
    try:
        return not entry.is_symlink() and entry.is_file(follow_symlinks=False)
    except OSError:
        return False
