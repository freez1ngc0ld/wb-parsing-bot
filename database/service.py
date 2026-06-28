from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, delete
from database.models import AllowedUsers, Products, ProductUsers, Checks
from schemas import ProductSchema, CheckPriceSchema
from config import settings


class WBService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_user_allowed(self, tg_id: int) -> bool:
        return bool((await self.db.execute(select(exists().where(AllowedUsers.tg_id == tg_id)))).scalar())
    
    async def get_product_by_wb_id(self, wb_id: int) -> Products | None:
        result = await self.db.execute(select(Products).where(Products.wb_id == wb_id))
        return result.scalar_one_or_none()
    
    async def get_user_by_tg_id(self, tg_id: int) -> AllowedUsers | None:
        result = await self.db.execute(select(AllowedUsers).where(AllowedUsers.tg_id == tg_id))
        return result.scalar_one_or_none()
    
    async def get_all_unique_products(self) -> list[ProductSchema]:
        result = await self.db.execute(select(Products).distinct(Products.wb_id))
        return [ProductSchema(id=product.id, wb_id=product.wb_id, wb_name=product.wb_name) for product in result.scalars().all()]
    
    async def get_product_owners(self, product: Products) -> list[AllowedUsers]:
        stmt = (
            select(AllowedUsers)
            .join(ProductUsers, AllowedUsers.id == ProductUsers.user_id)
            .where(ProductUsers.product_id == product.id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_product_owners_for_api(self, wb_id: int) -> list[int]:
        stmt = (
            select(AllowedUsers.tg_id) 
            .join(ProductUsers, AllowedUsers.id == ProductUsers.user_id)
            .join(Products, ProductUsers.product_id == Products.id)
            .where(Products.wb_id == wb_id)
            .order_by(AllowedUsers.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_allowed_user(self, tg_id: int, tg_id_4_add: int) -> dict:
        if tg_id != settings.ROOTID:
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}
        
        if await self.is_user_allowed(tg_id=tg_id_4_add):
            return {'status': 'error', 'detail': 'Пользователь уже добавлен', 'status_code': 400}
        
        allowed_user = AllowedUsers(tg_id=tg_id_4_add)
        self.db.add(allowed_user)
        try:
            await self.db.commit()
            return {'status': 'success'}
        except Exception as e:
            await self.db.rollback()
            return {'status': 'error', 'detail': f'Ошибка базы данных: {str(e)}', 'status_code': 500}
    
    async def add_wb_product(self, tg_id: int, wb_id: int, wb_name: str) -> dict:
        if not await self.is_user_allowed(tg_id=tg_id):
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}

        user = await self.get_user_by_tg_id(tg_id=tg_id)
        if not user:
            return {'status': 'error', 'detail': 'Пользователь не найден в системе', 'status_code': 404}

        try:
            product = await self.get_product_by_wb_id(wb_id=wb_id)
            
            if not product:
                product = Products(wb_id=wb_id, wb_name=wb_name)
                self.db.add(product)
                await self.db.flush()  

            query_link = select(exists().where(
                ProductUsers.product_id == product.id,
                ProductUsers.user_id == user.id
            ))

            already_linked = bool((await self.db.execute(query_link)).scalar())
            
            if already_linked:
                return {'status': 'error', 'detail': 'Вы уже отслеживаете этот товар', 'status_code': 400}

            product_user = ProductUsers(product_id=product.id, user_id=user.id)
            self.db.add(product_user)
            
            await self.db.commit()
            return {'status': 'success'}
            
        except Exception as e:
            await self.db.rollback()
            return {'status': 'error', 'detail': f'Ошибка базы данных: {str(e)}', 'status_code': 500}
        
    async def delete_allowed_user(self, tg_id: int, tg_id_4_delete: int) -> dict:
        if tg_id != settings.ROOTID:
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}
        user = await self.get_user_by_tg_id(tg_id=tg_id_4_delete)
        if not user:
            return {'status': 'error', 'detail': 'Пользователь не найден в системе', 'status_code': 404}
        try:
            await self.db.execute(delete(AllowedUsers).where(AllowedUsers.tg_id == tg_id_4_delete))
            await self.db.commit()
            return {'status': 'success'}
        except Exception as e:
            await self.db.rollback()
            return {'status': 'error', 'detail': f'Ошибка базы данных: {str(e)}', 'status_code': 500}

    async def delete_wb_product(self, tg_id: int, wb_id: int) -> dict:
        if not await self.is_user_allowed(tg_id=tg_id):
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}
        
        user = await self.get_user_by_tg_id(tg_id=tg_id)
        product = await self.get_product_by_wb_id(wb_id=wb_id)
        
        if not user or not product:
            return {'status': 'error', 'detail': 'Пользователь или товар не найдены в системе', 'status_code': 404}

        owners = await self.get_product_owners(product=product)
        
        if user.id not in [owner.id for owner in owners]:
            return {'status': 'error', 'detail': 'Вы не подписаны на данный товар', 'status_code': 400}

        try:
            await self.db.execute(
                delete(ProductUsers).where(
                    ProductUsers.product_id == product.id,
                    ProductUsers.user_id == user.id
                )
            )

            await self.db.flush()

            if len(owners) <= 1:
                await self.db.execute(delete(Products).where(Products.id == product.id))

            await self.db.commit()
            return {'status': 'success'}

        except Exception as e:
            await self.db.rollback()
            return {'status': 'error', 'detail': f'Ошибка базы данных: {str(e)}', 'status_code': 500}
        
    async def get_all_subscribes(self, tg_id: int, offset: int, limit: int) -> list[ProductSchema] | dict:
        if not await self.is_user_allowed(tg_id=tg_id):
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}
        stmt = (
            select(Products)
            .join(ProductUsers, ProductUsers.product_id == Products.id)   
            .join(AllowedUsers, AllowedUsers.id == ProductUsers.user_id)
            .where(AllowedUsers.tg_id == tg_id)
            .offset(offset)
            .limit(limit)
            .order_by(Products.created_at.desc())
        )
        products = (await self.db.execute(stmt)).scalars()
        return [ProductSchema(id=product.id, wb_id=product.wb_id, wb_name=product.wb_name) for product in products]
    
    async def get_product_prices(self, tg_id: int, wb_id: int, offset: int, limit: int) -> list[CheckPriceSchema] | dict:
        if not await self.is_user_allowed(tg_id=tg_id):
            return {'status': 'error', 'detail': 'У вас нет прав для данного действия', 'status_code': 403}
        stmt = (
            select(Checks)
            .join(Products, Products.id == Checks.product_id)
            .where(Products.wb_id == wb_id)
            .offset(offset)
            .limit(limit)
            .order_by(Checks.created_at.desc())
        )
        check_prices = (await self.db.execute(stmt)).scalars()
        return [CheckPriceSchema(wb_price=check_price.wb_price, created_at=check_price.created_at) for check_price in check_prices]

    async def add_price_check(self, product_id: str, wb_name: str, price: int) -> dict:
        try:
            product_query = select(Products).where(Products.id == product_id)
            product_res = await self.db.execute(product_query)
            product = product_res.scalar_one_or_none()
            
            if product and product.wb_name != wb_name:
                product.wb_name = wb_name

            check_query = (
                select(Checks)
                .where(Checks.product_id == product_id)
                .order_by(Checks.created_at.desc())
                .limit(1)
            )
            check_res = await self.db.execute(check_query)
            last_check = check_res.scalar_one_or_none()

            new_check = Checks(product_id=product_id, wb_price=price)
            self.db.add(new_check)
            
            should_notify = False
            percent_change = 0.0
            old_price_cop = None

            if last_check and last_check.wb_price > 0:
                old_price_cop = last_check.wb_price
                percent_change = abs(price - old_price_cop) / old_price_cop
                
                if percent_change >= 0.10:
                    should_notify = True

            await self.db.commit()
            
            return {
                'status': 'success',
                'should_notify': should_notify,
                'old_price': old_price_cop,
                'new_price': price,
                'percent_change': round(percent_change * 100, 2)
            }

        except Exception as e:
            await self.db.rollback()
            return {'status': 'error', 'detail': f'Ошибка при сохранении чека: {str(e)}', 'status_code': 500}
