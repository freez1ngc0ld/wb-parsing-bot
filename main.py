from fastapi import FastAPI, Depends, status, HTTPException
from database.service import WBService
from database.session import AsyncSessionLocal, AsyncSession, engine
from database.models import Base, AllowedUsers
from schemas import CheckUserResponseSchema, CreateOrDeleteProductSchema, ResponseSchema, ProductSchema,CheckPriceSchema
from contextlib import asynccontextmanager
from config import settings
from parser.parser import fetch_wb_product
import uvicorn


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()


def get_wb_service(db: AsyncSession = Depends(get_db)):
    return WBService(db=db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        root_id = int(settings.ROOTID)
        wb_service = WBService(db)
        if not await wb_service.is_user_allowed(tg_id=root_id):
            db.add(AllowedUsers(tg_id=root_id))
            await db.commit()
    yield


app = FastAPI(title='WB Parser API', version='1.1.0', lifespan=lifespan)


@app.get('/api/users/{tg_id}', response_model=CheckUserResponseSchema, status_code=status.HTTP_200_OK)
async def check_user_endpoint(tg_id: int, wb_service: WBService = Depends(get_wb_service)):
    allowed = await wb_service.is_user_allowed(tg_id=tg_id)
    return CheckUserResponseSchema(is_allowed=allowed)

@app.post('/api/users/{tg_id_4_add}', response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_user_endpoint(tg_id: int, tg_id_4_add: int, wb_service: WBService = Depends(get_wb_service)):
    data = await wb_service.add_allowed_user(tg_id=tg_id, tg_id_4_add=tg_id_4_add)
    if data['status'] != 'success':
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return ResponseSchema.model_validate(data)

@app.delete('/api/users/{tg_id_4_delete}', response_model=ResponseSchema, status_code=status.HTTP_200_OK)
async def delete_user_endpoint(tg_id: int, tg_id_4_delete: int, wb_service: WBService = Depends(get_wb_service)):
    data = await wb_service.delete_allowed_user(tg_id=tg_id, tg_id_4_delete=tg_id_4_delete)
    if data['status'] != 'success':
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return ResponseSchema.model_validate(data)

@app.get('/api/products/all', response_model=list[ProductSchema], status_code=status.HTTP_200_OK)
async def get_all_products(wb_service: WBService = Depends(get_wb_service)):
    return await wb_service.get_all_unique_products()

@app.get('/api/products/{wb_id}/owners', response_model=list[int], status_code=status.HTTP_200_OK)
async def get_all_product_owners(wb_id: int, wb_service: WBService = Depends(get_wb_service)):
    return await wb_service.get_product_owners_for_api(wb_id=wb_id)

@app.post('/api/products/', response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_product_endpoint(payload: CreateOrDeleteProductSchema, wb_service: WBService = Depends(get_wb_service)):
    parsed = await fetch_wb_product(payload.wb_id)
    if not parsed:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Ошибка при парсинге')
    wb_name, _ = parsed
    data = await wb_service.add_wb_product(tg_id=payload.tg_id, wb_id=payload.wb_id, wb_name=wb_name)
    if data['status'] != 'success':
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return ResponseSchema.model_validate(data)

@app.delete('/api/products/{wb_id}', response_model=ResponseSchema, status_code=status.HTTP_200_OK)
async def delete_product_endpoint(tg_id: int, wb_id: int, wb_service: WBService = Depends(get_wb_service)):
    data = await wb_service.delete_wb_product(tg_id=tg_id, wb_id=wb_id)
    if data['status'] != 'success':
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return ResponseSchema.model_validate(data)

@app.post('/api/checks/', response_model=ResponseSchema, status_code=status.HTTP_201_CREATED)
async def new_price_check(product_id: str, wb_name: str, price: int, wb_service: WBService = Depends(get_wb_service)):   
    data = await wb_service.add_price_check(product_id=product_id, wb_name=wb_name, price=price)
    if data['status'] != 'success':
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return ResponseSchema.model_validate(data)
    
@app.get('/api/products/', response_model=list[ProductSchema], status_code=status.HTTP_200_OK)
async def get_all_products(tg_id: int, offset: int = 0, limit: int = 10, wb_service: WBService = Depends(get_wb_service)):
    data = await wb_service.get_all_subscribes(tg_id=tg_id, offset=offset, limit=limit)
    if type(data) == dict:
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return data

@app.get('/api/checks/{wb_id}', response_model=list[CheckPriceSchema], status_code=status.HTTP_200_OK)
async def get_all_product_prices(tg_id: int, wb_id: int, offset: int = 0, limit: int = 10, wb_service: WBService = Depends(get_wb_service)):
    data = await wb_service.get_product_prices(tg_id=tg_id, wb_id=wb_id, offset=offset, limit=limit)
    if type(data) == dict:
        raise HTTPException(status_code=data['status_code'], detail=data['detail'])
    return data

if __name__ == '__main__':
    uvicorn.run(app='main:app', host=settings.API_HOST, port=settings.API_PORT, reload=True)
