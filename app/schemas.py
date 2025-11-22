# app/schemas.py
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, validator

from bson import ObjectId

# Small ObjectId wrapper for Pydantic
class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            # allow hex string that can be converted to ObjectId
            try:
                ObjectId(v)
                return v
            except Exception:
                raise ValueError("Invalid ObjectId string")
        raise TypeError("ObjectId or str required")

# User schemas
class UserCreate(BaseModel):
    name: str
    email: str
    hashed_password: str
    role: Optional[str] = 'customer'


class UserOut(BaseModel):
    id: PyObjectId = Field(..., alias='id')
    name: str
    email: str
    role: str
    created_at: Optional[datetime]



    class Config:
        orm_mode = True
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}


# Booking create schema
class BookingCreate(BaseModel):
    user_id: PyObjectId
    screening_id: PyObjectId
    seat_labels: List[str]
    total_amount: float = 0.0

# Screening create
class ScreeningCreate(BaseModel):
    movie_id: PyObjectId
    auditorium_id: PyObjectId
    start_time: datetime
    end_time: Optional[datetime] = None
    language: Optional[str] = None



# Basic validators can be added per-model as needed