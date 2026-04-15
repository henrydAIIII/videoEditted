from pydantic import BaseModel


class UploadResult(BaseModel):
    job_id: str
    stage: str

