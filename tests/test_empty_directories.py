from pathlib import Path

from app.services.empty_directories import (
    EmptyDirectoryScan,
    delete_empty_directories,
    scan_empty_directories,
)


def test_finds_and_deletes_regular_empty_directory(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    scan = scan_empty_directories(str(tmp_path), [tmp_path])

    assert scan.directories == [empty]
    result = delete_empty_directories(scan, [tmp_path])
    assert result.deleted == [empty]
    assert not empty.exists()


def test_nested_empty_directories_are_listed_deepest_first(tmp_path: Path) -> None:
    parent = tmp_path / "A"
    child = parent / "B"
    child.mkdir(parents=True)

    scan = scan_empty_directories(str(tmp_path), [tmp_path])

    assert scan.directories == [child, parent]
    result = delete_empty_directories(scan, [tmp_path])
    assert len(result.deleted) == 2
    assert not parent.exists()


def test_non_empty_directory_is_not_deleted(tmp_path: Path) -> None:
    directory = tmp_path / "has-file"
    directory.mkdir()
    (directory / "data.txt").write_text("content", encoding="utf-8")

    scan = scan_empty_directories(str(tmp_path), [tmp_path])
    result = delete_empty_directories(scan, [tmp_path])

    assert directory not in scan.directories
    assert result.deleted == []
    assert directory.exists()


def test_scan_root_is_never_listed_or_deleted(tmp_path: Path) -> None:
    scan = scan_empty_directories(str(tmp_path), [tmp_path])
    result = delete_empty_directories(scan, [tmp_path])

    assert scan.directories == []
    assert result.deleted == []
    assert tmp_path.exists()


def test_delete_rejects_root_even_if_scan_data_is_malformed(tmp_path: Path) -> None:
    malformed_scan = EmptyDirectoryScan(root=tmp_path, directories=[tmp_path])

    result = delete_empty_directories(malformed_scan, [tmp_path])

    assert result.deleted == []
    assert result.errors
    assert tmp_path.exists()


def test_directory_that_becomes_non_empty_after_scan_is_not_deleted(tmp_path: Path) -> None:
    directory = tmp_path / "empty-at-scan"
    directory.mkdir()
    scan = scan_empty_directories(str(tmp_path), [tmp_path])
    (directory / "new.txt").write_text("new", encoding="utf-8")

    result = delete_empty_directories(scan, [tmp_path])

    assert result.deleted == []
    assert result.errors
    assert directory.exists()
