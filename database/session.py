from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings

engine = create_async_engine(settings.DB_URL)
AsyncSessionLocal = async_sessionmaker[AsyncSession](bind=engine, expire_on_commit=False)

