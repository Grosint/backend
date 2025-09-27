from __future__ import annotations

from datetime import datetime
from enum import Enum

from bson import ObjectId
from pydantic import BaseModel


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


class SearchType(str, Enum):
    EMAIL = "email"
    DOMAIN = "domain"
    PHONE = "phone"
    USERNAME = "username"


class SearchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchBase(BaseModel):
    search_type: SearchType
    query: str
    user_id: PyObjectId


class SearchCreate(SearchBase):
    pass


class SearchUpdate(BaseModel):
    status: SearchStatus | None = None
    results_count: int | None = None
    error_message: str | None = None


class SearchInDB(SearchBase):
    id: PyObjectId = None
    status: SearchStatus = SearchStatus.PENDING
    results_count: int = 0
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class Search(SearchBase):
    id: PyObjectId = None
    status: SearchStatus
    results_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
