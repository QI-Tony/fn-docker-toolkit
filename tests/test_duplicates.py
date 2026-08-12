from pathlib import Path

from app.services.duplicates import (
    delete_duplicate_files,
    duplicate_group_id,
    scan_duplicate_files,
)


def test_identical_files_are_detected_as_duplicates(tmp_path: Path) -> None:
    first = tmp_path / "one.bin"
    second = tmp_path / "backup" / "two.bin"
    second.parent.mkdir()
    first.write_bytes(b"same contents" * 100)
    second.write_bytes(first.read_bytes())

    scan = scan_duplicate_files(str(tmp_path), [tmp_path])

    assert scan.scanned_files == 2
    assert len(scan.groups) == 1
    assert {file.path for file in scan.groups[0].files} == {first, second}
    assert scan.duplicate_files == 1
    assert scan.reclaimable_bytes == first.stat().st_size


def test_same_size_different_contents_are_not_duplicates(tmp_path: Path) -> None:
    (tmp_path / "one.bin").write_bytes(b"abcdef")
    (tmp_path / "two.bin").write_bytes(b"123456")

    scan = scan_duplicate_files(str(tmp_path), [tmp_path])

    assert scan.scanned_files == 2
    assert scan.groups == []


def test_changed_file_prevents_deletion_of_entire_group(tmp_path: Path) -> None:
    first = tmp_path / "one.bin"
    second = tmp_path / "two.bin"
    first.write_bytes(b"original")
    second.write_bytes(b"original")
    scan = scan_duplicate_files(str(tmp_path), [tmp_path])
    group = scan.groups[0]
    second.write_bytes(b"modified")

    result = delete_duplicate_files(
        scan, {duplicate_group_id(group): str(first)}, [tmp_path]
    )

    assert result.deleted == []
    assert result.errors
    assert first.exists()
    assert second.exists()


def test_selected_file_is_kept_and_other_copy_is_deleted(tmp_path: Path) -> None:
    first = tmp_path / "one.bin"
    second = tmp_path / "two.bin"
    first.write_bytes(b"duplicate")
    second.write_bytes(b"duplicate")
    scan = scan_duplicate_files(str(tmp_path), [tmp_path])
    group = scan.groups[0]

    result = delete_duplicate_files(
        scan, {duplicate_group_id(group): str(first)}, [tmp_path]
    )

    assert first.exists()
    assert not second.exists()
    assert result.deleted == [second]
    assert result.reclaimed_bytes == len(b"duplicate")
