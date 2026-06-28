import os
import asyncio
import httpx
from aiogram import Bot
from config import settings
from .broker import broker
from .parser import fetch_wb_product
from logger import logger

API_URL = f"http://web_api:{settings.API_PORT}/api"


async def parse_and_update_product(prod: dict, semaphore: asyncio.Semaphore, client: httpx.AsyncClient):
    async with semaphore:
        wb_id = prod.get('wb_id')
        product_uuid = prod.get('id')

        logger.info(f"[Worker PID: {os.getpid()}] Начинаю парсинг товара {wb_id}...")
        parsed = await fetch_wb_product(wb_id)
        if not parsed:
            return
        wb_name, new_price_cop = parsed

        try:
            resp = await client.get(
                f"{API_URL}/checks/{wb_id}", 
                params={"tg_id": 0, "offset": 0, "limit": 1}
            )
            prices = resp.json() if resp.status_code == 200 else []
            old_price_cop = prices[0].get("price", new_price_cop) if prices else new_price_cop
        except Exception:
            old_price_cop = new_price_cop

        diff = 0
        if old_price_cop > 0:
            diff = round(((new_price_cop - old_price_cop) / old_price_cop) * 100, 2)

        is_notify_time = abs(diff) >= settings.TRIGGER_PERCENT or settings.NOTIFY_ANYWAY

        if is_notify_time:
            msg_text = (
                f"🚨 **Мониторинг цен Wildberries**\n\n"
                f"📦 {wb_name}\n"
                f"📉 Было: {old_price_cop // 100} руб.\n"
                f"📈 Стало: {new_price_cop // 100} руб.\n"
                f"📊 Изменение: {diff}%"
            )
            
            try:
                owners_res = await client.get(f"{API_URL}/products/{wb_id}/owners")
                tg_ids = owners_res.json() if owners_res.status_code == 200 else []
                logger.info(f"Owners for {wb_id}: {tg_ids}")
                async with Bot(token=settings.TOKEN) as bot:
                    if tg_ids:
                        for tg_id in tg_ids:
                            await bot.send_message(chat_id=int(tg_id), text=msg_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Ошибка уведомления: {e}")

        try:
            await client.post(f"{API_URL}/checks/", params={
                "product_id": str(product_uuid),
                "wb_name": wb_name,
                "price": new_price_cop
            })
        except Exception as e:
            logger.error(f"Ошибка сохранения цены: {e}")

@broker.task(schedule=[{"interval": settings.TIME_CHECK}])
async def run_cron_monitoring():
    logger.info("Запуск мониторинга...")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(f"{API_URL}/products/all")
            products = response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Ошибка получения списка товаров: {e}")
            return

    if not products:
        logger.info("Список товаров пуст")
        return

    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=20.0) as client:
        tasks = [parse_and_update_product(prod, semaphore, client) for prod in products]
        await asyncio.gather(*tasks)
