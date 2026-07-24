"""文件上传 + OCR API"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlmodel import Session, select
from datetime import datetime, timezone
from pathlib import Path
import uuid
import json

from app.core.database import get_session
from app.core.config import settings
from app.models.file import File
from app.models.person import Person
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas import ApiResponse

router = APIRouter(prefix="/api/files", tags=["文件上传"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload")
async def upload_file(
    person_id: int,
    file_type: str = "扫描件",
    file: UploadFile = FastAPIFile(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """上传文件（扫描件/照片）"""
    # 校验人员存在
    person = session.get(Person, person_id)
    if not person or person.is_deleted:
        raise HTTPException(status_code=404, detail="人员不存在")

    # 校验文件类型
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    # 校验文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过{settings.MAX_FILE_SIZE_MB}MB限制")

    # 保存文件
    person_dir = Path(settings.UPLOAD_DIR) / str(person_id)
    person_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = person_dir / filename
    filepath.write_bytes(content)

    # 记录到数据库
    db_file = File(
        person_id=person_id,
        file_type=file_type,
        file_path=str(filepath),
        original_name=file.filename,
    )
    session.add(db_file)
    session.commit()
    session.refresh(db_file)

    return {"id": db_file.id, "file_path": str(filepath), "original_name": file.filename}


@router.get("/list/{person_id}")
def list_files(
    person_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """获取人员的文件列表"""
    files = session.exec(
        select(File).where(File.person_id == person_id).order_by(File.uploaded_at.desc())
    ).all()
    return files


@router.delete("/{file_id}", response_model=ApiResponse)
def delete_file(
    file_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """删除文件"""
    file = session.get(File, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 删除物理文件
    try:
        Path(file.file_path).unlink(missing_ok=True)
    except Exception:
        pass

    session.delete(file)
    session.commit()
    return ApiResponse(message="删除成功")
