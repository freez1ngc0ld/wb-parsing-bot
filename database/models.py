from sqlalchemy.orm import mapped_column, Mapped, DeclarativeBase
from sqlalchemy import String, func, DateTime, BigInteger, ForeignKey
from datetime import datetime
from uuid import uuid4


class Base(DeclarativeBase):
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

class AllowedUsers(Base):
    __tablename__ = 'allowed_users'
    
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False) 

class Products(Base):
    __tablename__ = 'products'

    wb_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False) 
    wb_name: Mapped[str] = mapped_column(String(255)) 

class ProductUsers(Base):
    __tablename__ = 'product_users'

    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('allowed_users.id', ondelete='CASCADE'), index=True)

class Checks(Base):
    __tablename__ = 'checks'

    product_id: Mapped[str] = mapped_column(ForeignKey('products.id', ondelete='CASCADE'), index=True)
    wb_price: Mapped[int] = mapped_column(BigInteger)
