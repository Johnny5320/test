"""文件管理 API — 路径收编（定稿 §3.4）：
GET/POST /api/persons/{person_id}/files、DELETE /api/files/{file_id}、
GET /api/files/download/{file_id}（文件流，middleware 白名单透传）。
上传分块读（1MB/块，超限提前终止）；删物理文件失败记 warning 不吞。
"""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File as FastAPIFile, Form, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_session
from app.models.user import User
from app.core.logging_config import log_call
from app.models.file import File
from app.models.person import Person
from app.schemas.common import BizError, ErrorCode, ok

logger = logging.getLogger("judicial.api.files")

router = APIRouter(tags=["文件管理"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024  # 1MB/块

# 文件魔数字节签名（用于校验文件内容与扩展名是否匹配）
MAGIC_SIGNATURES = {
    b'\x25\x50\x44\x46': '.pdf',      # %PDF
    b'\x89\x50\x4e\x47': '.png',      # .PNG
    b'\xff\xd8\xff': '.jpg',           # JPEG
    b'\x42\x4d': '.bmp',              # BMP
    b'\x49\x49\x2a\x00': '.tiff',     # TIFF (little-endian)
    b'\x4d\x4d\x00\x2a': '.tiff',     # TIFF (big-endian)
}


def _validate_file_header(content_start: bytes, expected_ext: str) -> None:
    """校验文件内容魔数与扩展名是否匹配，防止伪装扩展名上传恶意文件"""
    detected_ext = None
    for signature, ext in MAGIC_SIGNATURES.items():
        if content_start.startswith(signature):
            detected_ext = ext
            break
    if detected_ext and detected_ext != expected_ext:
        raise BizError(ErrorCode.FILE_TYPE_UNSUPPORTED,
                       f"文件内容与扩展名不匹配（检测为 {detected_ext}，声明为 {expected_ext}）")


def _get_person_or_404(session: Session, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if not person or person.is_deleted:
        raise BizError(ErrorCode.PERSON_NOT_FOUND, "人员不存在")
    return person


def _get_file_or_404(session: Session, file_id: int) -> File:
    file = session.get(File, file_id)
    if not file:
        raise BizError(ErrorCode.FILE_NOT_FOUND, "文件不存在")
    return file


@router.get("/api/persons/{person_id}/files")
@log_call
def list_person_files(person_id: int, session: Session = Depends(get_session),
                      current_user: User = Depends(get_current_user)):
    """获取人员的文件列表"""
    return session.exec(
        select(File).where(File.person_id == person_id)
        .order_by(File.uploaded_at.desc())
    ).all()


@router.post("/api/persons/{person_id}/files")
@log_call
async def upload_person_file(
    person_id: int,
    file: UploadFile = FastAPIFile(...),
    file_type: str = Form("扫描件"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """上传文件（扫描件/照片）— 分块读，超限提前终止并清理半成品"""
    _get_person_or_404(session, person_id)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BizError(ErrorCode.FILE_TYPE_UNSUPPORTED, f"不支持的文件类型: {ext}")

    person_dir = Path(settings.UPLOAD_DIR) / str(person_id)
    person_dir.mkdir(parents=True, exist_ok=True)
    filepath = person_dir / f"{uuid.uuid4().hex}{ext}"

    # 先读8字节校验魔数，再写入
    header = await file.read(8)
    if len(header) > 0:
        _validate_file_header(header, ext)

    size = len(header)
    try:
        with filepath.open("wb") as out:
            out.write(header)
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise BizError(ErrorCode.FILE_SIZE_EXCEEDED,
                                   f"文件超过{settings.MAX_FILE_SIZE_MB}MB限制")
                out.write(chunk)
    except Exception:
        filepath.unlink(missing_ok=True)
        raise

    # 路径绝对化：存储绝对路径并验证在 UPLOAD_DIR 内
    abs_path = filepath.resolve()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    if not str(abs_path).startswith(str(upload_root)):
        abs_path.unlink(missing_ok=True)
        raise BizError(ErrorCode.FILE_TYPE_UNSUPPORTED, "非法文件路径")

    db_file = File(person_id=person_id, file_type=file_type,
                   file_path=str(abs_path), original_name=file.filename)
    session.add(db_file)
    session.commit()
    session.refresh(db_file)
    return {"id": db_file.id, "file_path": str(abs_path),
            "original_name": file.filename}


@router.delete("/api/files/{file_id}")
@log_call
def delete_file(file_id: int, session: Session = Depends(get_session),
                current_user: User = Depends(get_current_user)):
    """删除文件 — 物理文件删除失败记 warning，不阻断 DB 删除"""
    file = _get_file_or_404(session, file_id)
    try:
        Path(file.file_path).unlink(missing_ok=True)
    except OSError as e:
        logger.warning("物理文件删除失败: %s (%s)", file.file_path, e)
    session.delete(file)
    session.commit()
    return ok(message="删除成功")


@router.get("/api/files/download/{file_id}")
@log_call
def download_file(file_id: int, session: Session = Depends(get_session),
                  current_user: User = Depends(get_current_user)):
    """下载文件 — 文件流，不参与信封（middleware 白名单）"""
    file = _get_file_or_404(session, file_id)
    path = Path(file.file_path).resolve()
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    if not str(path).startswith(str(upload_root)):
        raise BizError(ErrorCode.FILE_TYPE_UNSUPPORTED, "非法文件路径")
    if not path.exists():
        raise BizError(ErrorCode.FILE_NOT_FOUND, "物理文件不存在")
    return FileResponse(path, filename=file.original_name or path.name)
