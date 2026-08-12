from pathlib import Path

import pytest

from app.utils.filesystem import PathValidationError, validate_directory


def test_rejects_path_outside_allowed_roots(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()

    with pytest.raises(PathValidationError, match="不在允许范围"):
        validate_directory(str(outside), [allowed])


def test_rejects_parent_traversal_even_if_result_is_allowed(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    traversing = str(child / ".." / "child")

    with pytest.raises(PathValidationError, match="不允许"):
        validate_directory(traversing, [tmp_path])


def test_missing_path_has_clear_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(PathValidationError, match="路径不存在"):
        validate_directory(str(missing), [tmp_path])


def test_rejects_symlink_as_scan_path(tmp_path: Path) -> None:
    target = tmp_path / "target"
    link = tmp_path / "link"
    target.mkdir()
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("当前系统不允许创建 symbolic link")

    with pytest.raises(PathValidationError, match="symbolic link"):
        validate_directory(str(link), [tmp_path])
