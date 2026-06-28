import asyncio
import re
import sys
import httpx
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters.callback_data import CallbackData
from config import settings
from logger import logger

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

bot = Bot(token=settings.TOKEN)
dp = Dispatcher(storage=MemoryStorage())

API_URL = f"http://web_api:{settings.API_PORT}/api"
LIMIT_PER_PAGE = 10

class ProductActionCallback(CallbackData, prefix="prod"):
    action: str  
    wb_id: int

class PaginationCallback(CallbackData, prefix="page"):
    page: int

class SubscriptionsState(StatesGroup):
    viewing = State()

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить товар"), KeyboardButton(text="📋 Мои подписки")],
        ],
        resize_keyboard=True
    )

async def build_subscriptions_keyboard(tg_id: int, page: int = 0) -> InlineKeyboardMarkup:
    offset = page * LIMIT_PER_PAGE
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{API_URL}/products/", 
                params={"tg_id": tg_id, "offset": offset, "limit": LIMIT_PER_PAGE + 1}
            )
            if response.status_code != 200:
                return None
            products = response.json()
        except Exception as e:
            logger.error(f"Ошибка получения подписок: {e}")
            return None
    
    has_next = len(products) > LIMIT_PER_PAGE
    display_products = products[:LIMIT_PER_PAGE]
    keyboard_lines = []

    for prod in display_products:
        wb_id = prod['wb_id']
        name_short = prod['wb_name'][:18] + '...' if len(prod['wb_name']) > 18 else prod['wb_name']
        btn_stats = InlineKeyboardButton(
            text=f"📊 {name_short}", 
            callback_data=ProductActionCallback(action="stats", wb_id=wb_id).pack()
        )
        btn_delete = InlineKeyboardButton(
            text="🗑 Удалить", 
            callback_data=ProductActionCallback(action="del", wb_id=wb_id).pack()
        )
        keyboard_lines.append([btn_stats, btn_delete])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=PaginationCallback(page=page - 1).pack()))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=PaginationCallback(page=page + 1).pack()))
    if nav_row:
        keyboard_lines.append(nav_row)
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard_lines)

def get_wb_id_from_url(text: str) -> int | None:
    text = text.strip()
    if text.isdigit(): return int(text)
    match = re.search(r'wildberries\.ru/catalog/(\d+)', text)
    return int(match.group(1)) if match else None

@dp.message(Command('start'))
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Добро пожаловать в панель управления парсером WB!", reply_markup=get_main_keyboard())

@dp.message(F.text == "➕ Добавить товар")
async def text_add_product_help(message: Message) -> None:
    await message.answer("Отправьте мне ссылку на товар Wildberries или его цифровой артикул для добавления.")

@dp.message(F.text == "📋 Мои подписки")
async def show_subscriptions(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    kb = await build_subscriptions_keyboard(tg_id=tg_id, page=0)
    if not kb or not kb.inline_keyboard:
        await message.answer("У вас пока нет активных подписок на товары.")
        return
    await state.set_state(SubscriptionsState.viewing)
    await state.update_data(current_page=0)
    await message.answer("📋 Список ваших подписок:", reply_markup=kb)

@dp.callback_query(PaginationCallback.filter(), StateFilter(SubscriptionsState.viewing))
async def process_pagination(callback: CallbackQuery, callback_data: PaginationCallback, state: FSMContext):
    tg_id = callback.from_user.id
    target_page = callback_data.page
    kb = await build_subscriptions_keyboard(tg_id=tg_id, page=target_page)
    if kb:
        await state.update_data(current_page=target_page)
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

@dp.callback_query(ProductActionCallback.filter(F.action == "stats"), StateFilter(SubscriptionsState.viewing))
async def process_stats_callback(callback: CallbackQuery, callback_data: ProductActionCallback):
    tg_id = callback.from_user.id
    wb_id = callback_data.wb_id
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{API_URL}/checks/{wb_id}", params={"tg_id": tg_id, "offset": 0, "limit": 10})
    if res.status_code != 200:
        await callback.answer("Ошибка при запросе истории цен.", show_alert=True)
        return
    prices = res.json()
    if not prices:
        await callback.message.answer(f"История цен для товара `{wb_id}` пуста.", parse_mode="Markdown")
        await callback.answer()
        return
    text_lines = [f"📊 **Последние 10 обновлений цен для артикула {wb_id}:**\n"]
    for idx, check in enumerate(prices, 1):
        price_r = check['wb_price'] // 100
        date_clean = check['created_at'].replace("T", " ")[:16]
        text_lines.append(f"{idx}. `[{date_clean}]` — **{price_r} руб.**")
    await callback.message.answer("\n".join(text_lines), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(ProductActionCallback.filter(F.action == "del"), StateFilter(SubscriptionsState.viewing))
async def process_delete_callback(callback: CallbackQuery, callback_data: ProductActionCallback, state: FSMContext):
    tg_id = callback.from_user.id
    wb_id = callback_data.wb_id
    async with httpx.AsyncClient() as client:
        res = await client.request("DELETE", f"{API_URL}/products/{wb_id}", params={"tg_id": tg_id})
    if res.status_code == 200:
        await callback.answer("Подписка удалена!", show_alert=False)
        fsm_data = await state.get_data()
        current_page = fsm_data.get("current_page", 0)
        kb = await build_subscriptions_keyboard(tg_id=tg_id, page=current_page)
        if kb and kb.inline_keyboard:
            await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            await callback.message.edit_text("Все подписки удалены.")
            await state.clear()
    else:
        await callback.answer(f"Ошибка удаления: {res.json().get('detail')}", show_alert=True)

@dp.message(lambda msg: get_wb_id_from_url(msg.text) is not None)
async def add_product_via_bot(message: Message) -> None:
    wb_id = get_wb_id_from_url(message.text)
    tg_id = message.from_user.id
    status_msg = await message.answer("🔄 Обработка запроса...")
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            user_res = await client.get(f"{API_URL}/users/{tg_id}")
            if not user_res.json().get("is_allowed"):
                await status_msg.edit_text("❌ Доступ запрещен.")
                return
            res = await client.post(f"{API_URL}/products/", json={"tg_id": tg_id, "wb_id": wb_id})
            if res.status_code == 201:
                await status_msg.edit_text(f"✅ Товар `{wb_id}` успешно поставлен на мониторинг!", parse_mode="Markdown")
            else:
                await status_msg.edit_text(f"❌ Ошибка сервера: {res.json().get('detail')}")
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            await status_msg.edit_text("❌ Ошибка соединения с API.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
    