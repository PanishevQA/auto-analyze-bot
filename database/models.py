from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="Весь РФ")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    calculations: Mapped[list["Calculation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Calculation(Base):
    __tablename__ = "calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    car_data: Mapped[str] = mapped_column(Text, nullable=False)
    market_data: Mapped[str] = mapped_column(Text, nullable=False)
    repair_estimate: Mapped[str] = mapped_column(Text, nullable=False)
    scores: Mapped[str] = mapped_column(Text, nullable=False)
    final_report: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    user: Mapped[User] = relationship(back_populates="calculations")


engine = create_async_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
