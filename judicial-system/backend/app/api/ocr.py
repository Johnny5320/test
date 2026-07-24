"""OCR 识别 API"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile
from sqlmodel import Session
from pathlib import Path
import re
import uuid
import gc

from app.core.database import get_session
from app.core.config import settings
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/ocr", tags=["OCR识别"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".pdf"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def extract_fields(ocr_results: list) -> dict:
    """从OCR结果中提取结构化字段"""
    texts = [item[1] for item in ocr_results] if ocr_results else []
    full_text = "\n".join(texts)

    fields = {}

    # 提取身份证号（18位）
    id_card_match = re.search(r'(\d{17}[\dXx])', full_text)
    if id_card_match:
        id_card = id_card_match.group(1).upper()
        fields["id_card"] = id_card
        if len(id_card) == 18:
            fields["gender"] = "男" if int(id_card[16]) % 2 == 1 else "女"
            try:
                from datetime import datetime
                fields["birth_date"] = datetime.strptime(id_card[6:14], "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                pass

    # 提取姓名
    name_match = re.search(r'姓\s*名[：:\s]*([\u4e00-\u9fa5]{2,4})', full_text)
    if name_match:
        fields["name"] = name_match.group(1)

    # 提取电话
    phone_match = re.search(r'1[3-9]\d{9}', full_text)
    if phone_match:
        fields["phone"] = phone_match.group(0)

    # 提取地址
    addr_match = re.search(r'(?:住址|地址)[：:\s]*([\u4e00-\u9fa5\d]+(?:路|街|巷|号|村|镇|区|市|省)[\u4e00-\u9fa5\d]*)', full_text)
    if addr_match:
        fields["household_addr"] = addr_match.group(1)

    # 提取罪名
    crime_match = re.search(r'罪\s*名[：:]*\s*([\u4e00-\u9fa5]+罪)', full_text)
    if not crime_match:
        crime_match = re.search(r'犯([\u4e00-\u9fa5]+罪)', full_text)
    if crime_match:
        fields["original_crime"] = crime_match.group(1)

    # 提取刑期
    sentence_match = re.search(r'(?:有期徒|刑期|判处)[^\d零一二三四五六七八九十]*([\d零一二三四五六七八九十]+年[\d零一二三四五六七八九十个]*月*|[\d零一二三四五六七八九十]+个月)', full_text)
    if sentence_match:
        fields["original_sentence"] = sentence_match.group(1)

    # 提取日期
    date_matches = re.findall(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', full_text)
    if date_matches:
        dates = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in date_matches]
        fields["dates_found"] = dates

    return fields


@router.post("/scan")
async def ocr_scan(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
):
    """上传文件并进行OCR识别"""
    # 读取文件
    content = await file.read()

    # 文件大小检查
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件超过{settings.MAX_FILE_SIZE_MB}MB限制")

    # 文件类型检查
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")

    tmp_path = Path(settings.UPLOAD_DIR) / f"tmp_{uuid.uuid4().hex}{ext}"
    tmp_path.write_bytes(content)

    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()

        all_results = []

        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(str(tmp_path))

            # 页数限制
            total_pages = len(doc)
            if total_pages > settings.OCR_MAX_PAGES:
                doc.close()
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF共{total_pages}页，超过{settings.OCR_MAX_PAGES}页限制，请拆分后上传",
                )

            scale = settings.OCR_SCALE
            for page_idx in range(total_pages):
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                img_path = Path(settings.UPLOAD_DIR) / f"tmp_page_{uuid.uuid4().hex}.png"
                img_path.write_bytes(pix.tobytes("png"))
                del pix  # 立即释放图片内存
                try:
                    result, _ = engine(str(img_path))
                    if result:
                        all_results.extend(result)
                finally:
                    img_path.unlink(missing_ok=True)
            doc.close()
            gc.collect()  # 强制回收PDF相关内存
        else:
            result, _ = engine(str(tmp_path))
            if result:
                all_results = result

        fields = extract_fields(all_results)

        return {
            "success": True,
            "pages": total_pages if ext == ".pdf" else 1,
            "raw_text": [item[1] for item in all_results] if all_results else [],
            "fields": fields,
            "confidence": sum(item[2] for item in all_results) / len(all_results) if all_results else 0,
        }
    except HTTPException:
        raise
    except ImportError:
        return {
            "success": False,
            "error": "OCR引擎未安装，请运行: pip install rapidocr-onnxruntime pymupdf",
            "raw_text": [],
            "fields": {},
        }
    except Exception:
        return {
            "success": False,
            "error": "OCR识别失败，请检查文件是否损坏",
            "raw_text": [],
            "fields": {},
        }
    finally:
        tmp_path.unlink(missing_ok=True)
