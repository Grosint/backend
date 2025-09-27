from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, Field


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema

        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class ResultBase(BaseModel):
    search_id: PyObjectId
    source: str
    data: dict[str, Any]
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)


class ResultCreate(ResultBase):
    pass


class ResultUpdate(BaseModel):
    data: dict[str, Any] | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)


class ResultInDB(ResultBase):
    id: PyObjectId = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Result(ResultBase):
    id: PyObjectId = None
    created_at: datetime
    updated_at: datetime

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
