from pathlib import Path

from app.services import duplicates
from app.services.duplicates import (
    DuplicateStrategy,
    delete_duplicate_files,
    duplicate_group_id,
    scan_duplicate_files,
)
from app.utils.audio import AudioFingerprint, AudioInfo


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


def test_same_filename_strategy_finds_different_contents(tmp_path: Path) -> None:
    first = tmp_path / "album-one" / "song.wav"
    second = tmp_path / "album-two" / "SONG.WAV"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first version")
    second.write_bytes(b"a different and longer version")

    scan = scan_duplicate_files(str(tmp_path), [tmp_path], DuplicateStrategy.FILENAME)

    assert scan.strategy == DuplicateStrategy.FILENAME
    assert len(scan.groups) == 1
    assert scan.groups[0].confidence == "review"
    assert {file.path for file in scan.groups[0].files} == {first, second}


def test_pcm_strategy_ignores_container_byte_differences(
    tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "album-one" / "song.wav"
    second = tmp_path / "album-two" / "song.wav"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"header-one plus the same pcm")
    second.write_bytes(b"a much longer metadata header plus the same pcm")

    monkeypatch.setattr(duplicates, "require_programs", lambda *programs: None)
    monkeypatch.setattr(
        duplicates,
        "probe_audio",
        lambda path: AudioInfo(duration=180.0, sample_rate=44100, channels=2),
    )
    monkeypatch.setattr(duplicates, "pcm_sha256", lambda path: "a" * 64)

    scan = scan_duplicate_files(str(tmp_path), [tmp_path], DuplicateStrategy.AUDIO_PCM)

    assert len(scan.groups) == 1
    assert scan.groups[0].strategy == DuplicateStrategy.AUDIO_PCM
    assert scan.groups[0].confidence == "high"


def test_similar_audio_strategy_groups_close_fingerprints(
    tmp_path: Path, monkeypatch
) -> None:
    first = tmp_path / "original.wav"
    second = tmp_path / "remaster.wav"
    different = tmp_path / "other.wav"
    first.write_bytes(b"original bytes")
    second.write_bytes(b"remastered bytes")
    different.write_bytes(b"another song")

    fingerprints = {
        first: AudioFingerprint(200.0, tuple([0xAAAAAAAA] * 20)),
        second: AudioFingerprint(201.0, tuple([0xAAAAAAAA] * 20)),
        different: AudioFingerprint(200.0, tuple([0x55555555] * 20)),
    }
    monkeypatch.setattr(duplicates, "require_programs", lambda *programs: None)
    monkeypatch.setattr(
        duplicates, "chromaprint_file", lambda path: fingerprints[path]
    )

    scan = scan_duplicate_files(
        str(tmp_path), [tmp_path], DuplicateStrategy.AUDIO_SIMILAR
    )

    assert len(scan.groups) == 1
    assert {file.path for file in scan.groups[0].files} == {first, second}
    assert scan.groups[0].confidence == "review"
