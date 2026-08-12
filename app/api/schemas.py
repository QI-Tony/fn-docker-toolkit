from typing import Literal

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class DuplicateScanRequest(ScanRequest):
    strategy: Literal["exact", "audio_pcm", "audio_similar", "filename"] = "exact"


class ConfirmRequest(BaseModel):
    scan_token: str = Field(min_length=1)


class KeepSelection(BaseModel):
    group_id: str
    keep_path: str


class DuplicateDeleteRequest(ConfirmRequest):
    selections: list[KeepSelection]
