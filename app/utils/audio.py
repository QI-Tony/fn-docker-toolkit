from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess


AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".ape",
    ".dsf",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


class AudioToolError(RuntimeError):
    """Raised when an audio helper is unavailable or cannot analyze a file."""


@dataclass(frozen=True)
class AudioInfo:
    duration: float
    sample_rate: int
    channels: int


@dataclass(frozen=True)
class AudioFingerprint:
    duration: float
    values: tuple[int, ...]


def is_audio_file(path: Path) -> bool:
    return path.suffix.casefold() in AUDIO_EXTENSIONS


def require_programs(*programs: str) -> None:
    missing = [program for program in programs if shutil.which(program) is None]
    if missing:
        names = ", ".join(missing)
        raise AudioToolError(f"当前环境缺少音频分析工具：{names}")


def _run(command: list[str], timeout: int = 600) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AudioToolError(f"找不到音频分析工具：{command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioToolError(f"音频分析超时：{command[-1]}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        message = detail[-1] if detail else "未知错误"
        raise AudioToolError(f"音频分析失败：{message}")
    return completed.stdout.strip()


def probe_audio(path: Path) -> AudioInfo:
    output = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=sample_rate,channels,duration:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        payload = json.loads(output)
        stream = payload["streams"][0]
        duration_value = stream.get("duration") or payload.get("format", {}).get(
            "duration"
        )
        duration = float(duration_value)
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioToolError(f"无法读取音频参数：{path}") from exc
    if duration <= 0 or sample_rate <= 0 or channels <= 0:
        raise AudioToolError(f"音频参数无效：{path}")
    return AudioInfo(duration, sample_rate, channels)


def pcm_sha256(path: Path) -> str:
    """Hash decoded PCM frames while ignoring container metadata."""
    output = _run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-c:a",
            "pcm_s32le",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
    )
    match = re.search(r"SHA256=([0-9a-fA-F]{64})", output)
    if not match:
        raise AudioToolError(f"无法取得 PCM 哈希：{path}")
    return match.group(1).lower()


def chromaprint_file(path: Path) -> AudioFingerprint:
    output = _run(["fpcalc", "-json", "-raw", str(path)])
    try:
        payload = json.loads(output)
        duration = float(payload["duration"])
        raw_fingerprint = payload["fingerprint"]
        if isinstance(raw_fingerprint, str):
            values = tuple(
                int(value) for value in raw_fingerprint.split(",") if value.strip()
            )
        else:
            values = tuple(int(value) for value in raw_fingerprint)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioToolError(f"无法取得音频指纹：{path}") from exc
    if duration <= 0 or not values:
        raise AudioToolError(f"音频指纹为空：{path}")
    return AudioFingerprint(duration, values)


def fingerprint_similarity(
    first: tuple[int, ...], second: tuple[int, ...], max_shift: int = 4
) -> float:
    """Return the best aligned bit similarity between raw Chromaprint values."""
    best = 0.0
    for shift in range(-max_shift, max_shift + 1):
        first_start = max(0, shift)
        second_start = max(0, -shift)
        overlap = min(len(first) - first_start, len(second) - second_start)
        if overlap < 8:
            continue
        equal_bits = 0
        for index in range(overlap):
            left = first[first_start + index] & 0xFFFFFFFF
            right = second[second_start + index] & 0xFFFFFFFF
            equal_bits += 32 - (left ^ right).bit_count()
        best = max(best, equal_bits / (overlap * 32))
    return best
