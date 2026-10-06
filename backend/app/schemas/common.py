from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


Role = Literal["admin", "nurse", "clinician"]
DeviceStatus = Literal["inactive", "active", "maintenance", "retired"]
SessionStatus = Literal["active", "completed", "stopped"]


class Timestamped(BaseModel):
    created_at: datetime


PositiveId = Annotated[int, Field(gt=0)]
