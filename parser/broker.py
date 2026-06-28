import os
import sys
import asyncio
from taskiq_redis import PubSubBroker, RedisAsyncResultBackend
from taskiq.scheduler.scheduler import TaskiqScheduler
from taskiq.schedule_sources import LabelScheduleSource
from config import settings

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

REDIS_URL = settings.REDIS_URL

broker = PubSubBroker(
    url=REDIS_URL
).with_result_backend(
    RedisAsyncResultBackend(redis_url=REDIS_URL)
)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)]
)