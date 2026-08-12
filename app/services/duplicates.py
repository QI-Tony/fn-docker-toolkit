from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import os
from pathlib import Path
from typing import Callable, Iterable
import unicodedata

from app.utils.audio import (
    AudioFingerprint,
    AudioInfo,
    AudioToolError,
    chromaprint_file,
    fingerprint_similarity,
    is_audio_file,
    pcm_sha256,
    probe_audio,
    require_programs,
)
from app.utils.filesystem import (
    PathValidationError,
    describe_os_error,
    ensure_safe_child,
    validate_directory,
)
from app.utils.hashing import md5_file


class DuplicateStrategy(StrEnum):
    EXACT = "exact"
    AUDIO_PCM = "audio_pcm"
    AUDIO_SIMILAR = "audio_similar"
    FILENAME = "filename"


STRATEGY_LABELS = {
    DuplicateStrategy.EXACT: "精确文件重复",
    DuplicateStrategy.AUDIO_PCM: "PCM 音频内容相同",
    DuplicateStrategy.AUDIO_SIMILAR: "相似音频",
    DuplicateStrategy.FILENAME: "同名文件",
}


@dataclass(frozen=True)
class CollectedFile:
    path: Path
    size: int


@dataclass(frozen=True)
class DuplicateFile:
    path: Path
    size: int
    md5: str


@dataclass
class DuplicateGroup:
    strategy: DuplicateStrategy
    signature: str
    files: list[DuplicateFile]
    detail: str
    confidence: str

    @property
    def size(self) -> int | None:
        sizes = {file.size for file in self.files}
        return next(iter(sizes)) if len(sizes) == 1 else None

    @property
    def md5(self) -> str | None:
        return self.signature if self.strategy == DuplicateStrategy.EXACT else None

    @property
    def reclaimable_bytes(self) -> int:
        return sum(file.size for file in self.files[1:])


@dataclass
class DuplicateScan:
    root: Path
    strategy: DuplicateStrategy = DuplicateStrategy.EXACT
    scanned_files: int = 0
    analyzed_files: int = 0
    groups: list[DuplicateGroup] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duplicate_files(self) -> int:
        return sum(len(group.files) - 1 for group in self.groups)

    @property
    def reclaimable_bytes(self) -> int:
        return sum(group.reclaimable_bytes for group in self.groups)


@dataclass
class DuplicateDeletionResult:
    deleted: list[Path] = field(default_factory=list)
    reclaimed_bytes: int = 0
    errors: list[str] = field(default_factory=list)


def duplicate_group_id(group: DuplicateGroup) -> str:
    identity = "\0".join(
        [group.strategy.value, group.signature]
        + sorted(str(file.path) for file in group.files)
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _collect_files(directory: Path, scan: DuplicateScan) -> list[CollectedFile]:
    collected: list[CollectedFile] = []

    def visit(current: Path) -> None:
        try:
            with os.scandir(current) as iterator:
                entries = list(iterator)
        except OSError as exc:
            scan.errors.append(describe_os_error(current, exc))
            return

        for entry in entries:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False):
                    collected.append(
                        CollectedFile(path, entry.stat(follow_symlinks=False).st_size)
                    )
                    scan.scanned_files += 1
            except OSError as exc:
                scan.errors.append(describe_os_error(path, exc))

    visit(directory)
    return collected


def _snapshot_file(
    item: CollectedFile, scan: DuplicateScan, analyzer: Callable[[Path], str] | None = None
) -> tuple[DuplicateFile, str | None]:
    before = item.path.stat()
    analysis = analyzer(item.path) if analyzer else None
    digest = md5_file(item.path)
    after = item.path.stat()
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or after.st_size != item.size
    ):
        raise OSError("文件在扫描期间发生变化")
    scan.analyzed_files += 1
    return DuplicateFile(item.path, after.st_size, digest), analysis


def _append_group(
    scan: DuplicateScan,
    strategy: DuplicateStrategy,
    signature: str,
    files: list[DuplicateFile],
    detail: str,
    confidence: str,
) -> None:
    if len(files) > 1:
        scan.groups.append(
            DuplicateGroup(
                strategy,
                signature,
                sorted(files, key=lambda file: str(file.path)),
                detail,
                confidence,
            )
        )


def _scan_exact(files: list[CollectedFile], scan: DuplicateScan) -> None:
    by_size: dict[int, list[CollectedFile]] = defaultdict(list)
    for item in files:
        by_size[item.size].append(item)

    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_hash: dict[str, list[DuplicateFile]] = defaultdict(list)
        for item in candidates:
            try:
                snapshot, _ = _snapshot_file(item, scan)
                by_hash[snapshot.md5].append(snapshot)
            except OSError as exc:
                scan.errors.append(describe_os_error(item.path, exc))
        for digest, matching in by_hash.items():
            _append_group(
                scan,
                DuplicateStrategy.EXACT,
                digest,
                matching,
                f"{size} 字节 · MD5 {digest}",
                "exact",
            )


def _normalized_filename(path: Path) -> str:
    return unicodedata.normalize("NFC", path.name).casefold()


def _scan_filenames(files: list[CollectedFile], scan: DuplicateScan) -> None:
    by_name: dict[str, list[CollectedFile]] = defaultdict(list)
    for item in files:
        by_name[_normalized_filename(item.path)].append(item)

    for normalized_name, candidates in by_name.items():
        if len(candidates) < 2:
            continue
        snapshots: list[DuplicateFile] = []
        for item in candidates:
            try:
                snapshot, _ = _snapshot_file(item, scan)
                snapshots.append(snapshot)
            except OSError as exc:
                scan.errors.append(describe_os_error(item.path, exc))
        _append_group(
            scan,
            DuplicateStrategy.FILENAME,
            normalized_name,
            snapshots,
            f"文件名：{candidates[0].path.name}",
            "review",
        )


def _audio_candidate_key(info: AudioInfo) -> tuple[int, int, int]:
    return info.sample_rate, info.channels, round(info.duration * 100)


def _scan_audio_pcm(files: list[CollectedFile], scan: DuplicateScan) -> None:
    require_programs("ffprobe", "ffmpeg")
    by_properties: dict[tuple[int, int, int], list[CollectedFile]] = defaultdict(list)
    audio_info: dict[Path, AudioInfo] = {}
    for item in files:
        if not is_audio_file(item.path):
            continue
        try:
            info = probe_audio(item.path)
            audio_info[item.path] = info
            by_properties[_audio_candidate_key(info)].append(item)
        except (OSError, AudioToolError) as exc:
            scan.errors.append(f"{item.path}: {exc}")

    for candidates in by_properties.values():
        if len(candidates) < 2:
            continue
        by_pcm_hash: dict[str, list[DuplicateFile]] = defaultdict(list)
        for item in candidates:
            try:
                snapshot, pcm_hash = _snapshot_file(item, scan, pcm_sha256)
                if pcm_hash:
                    by_pcm_hash[pcm_hash].append(snapshot)
            except (OSError, AudioToolError) as exc:
                scan.errors.append(f"{item.path}: {exc}")
        for pcm_hash, matching in by_pcm_hash.items():
            info = audio_info[matching[0].path]
            _append_group(
                scan,
                DuplicateStrategy.AUDIO_PCM,
                pcm_hash,
                matching,
                (
                    f"PCM SHA-256 {pcm_hash} · {info.sample_rate} Hz · "
                    f"{info.channels} 声道"
                ),
                "high",
            )


def _duration_is_close(first: float, second: float) -> bool:
    return abs(first - second) <= max(3.0, min(first, second) * 0.02)


def _scan_similar_audio(files: list[CollectedFile], scan: DuplicateScan) -> None:
    require_programs("fpcalc")
    analyzed: list[tuple[CollectedFile, DuplicateFile, AudioFingerprint]] = []
    for item in files:
        if not is_audio_file(item.path):
            continue
        try:
            fingerprint_holder: list[AudioFingerprint] = []

            def analyze(path: Path) -> str:
                fingerprint = chromaprint_file(path)
                fingerprint_holder.append(fingerprint)
                return "chromaprint"

            snapshot, _ = _snapshot_file(item, scan, analyze)
            analyzed.append((item, snapshot, fingerprint_holder[0]))
        except (OSError, AudioToolError) as exc:
            scan.errors.append(f"{item.path}: {exc}")

    parent = list(range(len(analyzed)))
    pair_scores: dict[tuple[int, int], float] = {}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    ordered = sorted(range(len(analyzed)), key=lambda index: analyzed[index][2].duration)
    for position, first_index in enumerate(ordered):
        first_fingerprint = analyzed[first_index][2]
        for second_index in ordered[position + 1 :]:
            second_fingerprint = analyzed[second_index][2]
            if not _duration_is_close(first_fingerprint.duration, second_fingerprint.duration):
                if second_fingerprint.duration - first_fingerprint.duration > max(
                    3.0, first_fingerprint.duration * 0.02
                ):
                    break
                continue
            score = fingerprint_similarity(
                first_fingerprint.values, second_fingerprint.values
            )
            if score >= 0.88:
                pair_scores[(min(first_index, second_index), max(first_index, second_index))] = score
                union(first_index, second_index)

    clusters: dict[int, list[int]] = defaultdict(list)
    for index in range(len(analyzed)):
        clusters[find(index)].append(index)

    for indexes in clusters.values():
        if len(indexes) < 2:
            continue
        relevant_scores = [
            score
            for (first, second), score in pair_scores.items()
            if first in indexes and second in indexes
        ]
        minimum_score = min(relevant_scores) if relevant_scores else 0.88
        snapshots = [analyzed[index][1] for index in indexes]
        signature = hashlib.sha256(
            "\0".join(sorted(str(file.path) for file in snapshots)).encode("utf-8")
        ).hexdigest()
        _append_group(
            scan,
            DuplicateStrategy.AUDIO_SIMILAR,
            signature,
            snapshots,
            f"Chromaprint 相似度至少 {minimum_score:.0%}（需人工确认）",
            "review",
        )


def scan_duplicate_files(
    user_path: str,
    allowed_roots: Iterable[Path],
    strategy: DuplicateStrategy | str = DuplicateStrategy.EXACT,
) -> DuplicateScan:
    root = validate_directory(user_path, allowed_roots)
    selected_strategy = DuplicateStrategy(strategy)
    scan = DuplicateScan(root=root, strategy=selected_strategy)
    files = _collect_files(root, scan)

    scanners = {
        DuplicateStrategy.EXACT: _scan_exact,
        DuplicateStrategy.AUDIO_PCM: _scan_audio_pcm,
        DuplicateStrategy.AUDIO_SIMILAR: _scan_similar_audio,
        DuplicateStrategy.FILENAME: _scan_filenames,
    }
    scanners[selected_strategy](files, scan)
    scan.groups.sort(
        key=lambda group: (
            -max(file.size for file in group.files),
            str(group.files[0].path),
        )
    )
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

        validated: list[tuple[Path, DuplicateFile]] = []
        validation_error: str | None = None
        for file in group.files:
            try:
                safe_path = ensure_safe_child(file.path, scan.root, allowed_roots)
                stat = safe_path.stat()
                if not safe_path.is_file() or stat.st_size != file.size:
                    raise ValueError("文件大小已发生变化")
                if md5_file(safe_path) != file.md5:
                    raise ValueError("文件内容已发生变化")
                validated.append((safe_path, file))
            except (OSError, ValueError, PathValidationError) as exc:
                validation_error = f"{file.path}: {exc}"
                break

        if validation_error:
            result.errors.append(
                f"重复组 {group_id} 校验失败，整组未删除：{validation_error}"
            )
            continue

        for path, file in validated:
            if str(path) == selected:
                continue
            try:
                path.unlink()
                result.deleted.append(path)
                result.reclaimed_bytes += file.size
            except OSError as exc:
                result.errors.append(describe_os_error(path, exc))
    return result
