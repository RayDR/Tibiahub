from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class HuntBase(BaseModel):
    name: str
    location: str
    level_min: int
    level_max: int
    vocation: Optional[str] = None
    exp_per_hour: Optional[int] = None
    profit_per_hour: Optional[int] = None
    creatures: str
    strategy: Optional[str] = None
    notes: Optional[str] = None

class HuntCreate(HuntBase):
    pass

class HuntUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    level_min: Optional[int] = None
    level_max: Optional[int] = None
    vocation: Optional[str] = None
    exp_per_hour: Optional[int] = None
    profit_per_hour: Optional[int] = None
    creatures: Optional[str] = None
    strategy: Optional[str] = None
    notes: Optional[str] = None

class Hunt(HuntBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
