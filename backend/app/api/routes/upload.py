from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.core.responses import success_response
from app.schemas.upload import UploadResult

router = APIRouter(tags=["upload"])

UPLOAD_TARGETS = {
    "ppt_video": "ppt_video",
    "speaker_video": "speaker_video",
    "subtitles": "subtitles",
}


def _target_path(job_dir: Path, target_name: str, filename: str) -> Path:
    suffix = Path(filename).suffix or ""
    return job_dir / f"{target_name}{suffix}"


def _save_upload(target_path: Path, upload_file: UploadFile) -> None:
    upload_file.file.seek(0)
    with target_path.open("wb") as output_file:
        output_file.write(upload_file.file.read())


@router.post("/upload")
def upload_assets(
    ppt_video: UploadFile = File(...),
    speaker_video: UploadFile = File(...),
    subtitles: UploadFile = File(...),
) -> dict:
    settings = get_settings()
    job_id = uuid4().hex
    job_dir = settings.assets_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    files = {
        "ppt_video": ppt_video,
        "speaker_video": speaker_video,
        "subtitles": subtitles,
    }

    saved_files: dict[str, str] = {}
    for field_name, upload_file in files.items():
        target_name = UPLOAD_TARGETS[field_name]
        target_path = _target_path(job_dir, target_name, upload_file.filename or target_name)
        _save_upload(target_path, upload_file)
        saved_files[field_name] = target_path.name

    metadata = {
        "job_id": job_id,
        "status": "pending",
        "current_stage": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": saved_files,
    }

    with (job_dir / "job.json").open("w", encoding="utf-8") as metadata_file:
        json.dump(metadata, metadata_file, ensure_ascii=False, indent=2)

    result = UploadResult(job_id=job_id, stage="pending")
    return success_response(result.model_dump(), message="upload success")
