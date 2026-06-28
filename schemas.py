from pydantic import BaseModel
from datetime import datetime


class CheckUserResponseSchema(BaseModel):
    is_allowed: bool

class CreateOrDeleteProductSchema(BaseModel):
    tg_id: int
    wb_id: int

class ResponseSchema(BaseModel):
    status: str = 'success'
    detail: str = ''

class ProductSchema(BaseModel):
    id: str
    wb_id: int
    wb_name: str

class CheckPriceSchema(BaseModel):
    wb_price: int
    created_at: datetime
