from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    file_type: str
    created_at: datetime
    updated_at: datetime


class ResumeUploadResponse(ResumeResponse):
    file_size_bytes: int