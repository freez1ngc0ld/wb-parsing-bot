import asyncio
import random
from functools import wraps
from curl_cffi import requests
from logger import logger

IMP_LIST = ["chrome120", "chrome116", "firefox117", "safari17", "edge118", "opera100", "chrome", "firefox", "safari", "chrome_android", "safari_ios"]


def retry_with_impersonate(max_retries=len(IMP_LIST)):
    def decorator(func):
        wraps(func)
        async def wrapper(*args, **kwargs):
            used_agents = set()
            
            for attempt in range(1, max_retries + 1):
                available_agents = list(set(IMP_LIST) - used_agents)
                if not available_agents:
                    used_agents.clear()
                    available_agents = IMP_LIST.copy()
                
                agent = random.choice(available_agents)
                used_agents.add(agent)

                kwargs['impersonate_agent'] = agent
                
                logger.info(f"[Попытка {attempt}/{max_retries}] Пробуем отпечаток: {agent}")
                
                try:
                    result = await func(*args, **kwargs)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.warning(f"Ошибка выполнения функции с {agent}: {e}")

                if attempt < max_retries:
                    wait_time = attempt * 2
                    logger.info(f"Ожидание {wait_time} сек перед следующим ретраем...\n")
                    await asyncio.sleep(wait_time)
            logger.error(f"[Финал] Превышено число попыток ({max_retries}).")
            return None
        return wrapper
    return decorator


@retry_with_impersonate(max_retries=len(IMP_LIST))
async def fetch_wb_product(wb_id: int, impersonate_agent: str = None, session: requests.AsyncSession = None):
    url = f"https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={wb_id}"
    
    local_session = session or requests.AsyncSession()
    
    try:
        response = await local_session.get(url, impersonate=impersonate_agent, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if not data or 'products' not in data or not data['products']:
                logger.error(f"Товар с артикулом {wb_id} не найден на WB.")
                return None
            
            product = data['products'][0]
            name = product.get('name')

            price_raw = None
            for size in product.get('sizes', []):
                if 'price' in size:
                    price_raw = size['price'].get('product')
                    break
            
            if price_raw is None:
                logger.error(f"Товар '{name}' сейчас не в наличии (нет цен).")
                return None
                
            logger.info(f"Успешно распарсили: {name} -> {price_raw} коп.")

            return name, price_raw
        
        logger.info(f"Сервер вернул статус {response.status_code}")
        return None  
        
    except Exception as e:
        logger.warning(f"Ошибка при парсинге JSON: {e}")
        return None
    finally:
        if session is None:
            await local_session.close()

