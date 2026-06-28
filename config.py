import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    TOKEN = os.getenv('TOKEN')
    API_HOST = os.getenv('API_HOST')
    API_PORT = int(os.getenv('API_PORT'))
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = int(os.getenv('DB_PORT'))
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    REDIS_HOST = os.getenv('REDIS_HOST')
    REDIS_PORT = int(os.getenv('REDIS_PORT'))
    ROOTID = int(os.getenv('ROOTID'))
    TRIGGER_PERCENT = int(os.getenv('TRIGGER_PERCENT'))
    NOTIFY_ANYWAY = bool(os.getenv('NOTIFY_ANYWAY'))
    TIME_CHECK = int(os.getenv('TIME_CHECK'))

    # @property
    # def DB_URL(self):
    #     return 'sqlite+aiosqlite:///wb_db.sqlite3'

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def REDIS_URL(self):
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

settings = Settings()