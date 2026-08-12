from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import DuplicateDeleteRequest, ScanRequest
from app.services.duplicates import (
    DuplicateScan,
    delete_duplicate_files,
    duplicate_group_id,
    scan_duplicate_files,
)
from app.services.scan_registry import ScanRegistry
from app.utils.filesystem import PathValidationError


router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])
registry: ScanRegistry[DuplicateScan] = ScanRegistry()


@router.post("/scan")
def scan(payload: ScanRequest, request: Request) -> dict[str, object]:
    try:
        result = scan_duplicate_files(payload.path, request.app.state.settings.allowed_roots)
    except PathValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = registry.put(result)
    return {
        "scan_token": token,
        "root": str(result.root),
        "scanned_files": result.scanned_files,
        "duplicate_groups": len(result.groups),
        "duplicate_files": result.duplicate_files,
        "reclaimable_bytes": result.reclaimable_bytes,
        "groups": [
            {
                "id": duplicate_group_id(group),
                "size": group.size,
                "md5": group.md5,
                "files": [str(file.path) for file in group.files],
            }
            for group in result.groups
        ],
        "errors": result.errors,
    }


@router.post("/delete")
def delete(payload: DuplicateDeleteRequest, request: Request) -> dict[str, object]:
    scan_result = registry.take(payload.scan_token)
    if scan_result is None:
        raise HTTPException(status_code=409, detail="扫描结果不存在、已使用或已过期，请重新扫描")
    selections = {item.group_id: item.keep_path for item in payload.selections}
    result = delete_duplicate_files(
        scan_result, selections, request.app.state.settings.allowed_roots
    )
    return {
        "deleted": [str(path) for path in result.deleted],
        "deleted_count": len(result.deleted),
        "reclaimed_bytes": result.reclaimed_bytes,
        "errors": result.errors,
    }
