from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import ConfirmRequest, ScanRequest
from app.services.empty_directories import (
    EmptyDirectoryScan,
    delete_empty_directories,
    scan_empty_directories,
)
from app.services.scan_registry import ScanRegistry
from app.utils.filesystem import PathValidationError


router = APIRouter(prefix="/api/empty-directories", tags=["empty-directories"])
registry: ScanRegistry[EmptyDirectoryScan] = ScanRegistry()


@router.post("/scan")
def scan(payload: ScanRequest, request: Request) -> dict[str, object]:
    try:
        result = scan_empty_directories(payload.path, request.app.state.settings.allowed_roots)
    except PathValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = registry.put(result)
    return {
        "scan_token": token,
        "root": str(result.root),
        "directories": [str(path) for path in result.directories],
        "errors": result.errors,
    }


@router.post("/delete")
def delete(payload: ConfirmRequest, request: Request) -> dict[str, object]:
    scan_result = registry.take(payload.scan_token)
    if scan_result is None:
        raise HTTPException(status_code=409, detail="扫描结果不存在、已使用或已过期，请重新扫描")
    result = delete_empty_directories(
        scan_result, request.app.state.settings.allowed_roots
    )
    return {
        "deleted": [str(path) for path in result.deleted],
        "deleted_count": len(result.deleted),
        "errors": result.errors,
    }

