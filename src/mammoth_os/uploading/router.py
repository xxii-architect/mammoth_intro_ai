# router.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from .storage import save_file, delete_file
from .metadata import FileMetadata, register_file, get_file_metadata
from datetime import datetime
router = APIRouter()

@router.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_id = await save_file(file)
        metadata = FileMetadata(
            id=file_id,
            original_name=file.filename,
            size=file.file._file.tell(),
            content_type=file.content_type,
            created_at=datetime.now(),
            owner="user@example.com"  # Replace with actual user logic
        )
        register_file(metadata)
        return {"id": file_id, "original_name": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/v1/files/{id}")
async def get_file(id: str):
    metadata = get_file_metadata(id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    return metadata

@router.delete("/api/v1/files/{id}")
async def delete_file_route(id: str):
    try:
        delete_file(id)
        return {"detail": "File deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))