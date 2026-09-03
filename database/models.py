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
    analysis_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="COMPLETED")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")
    photos_metadata: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    condition_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    market_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNAVAILABLE")
    vision_status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNAVAILABLE")
    model_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    catalog_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formula_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_calculation_id: Mapped[int | None] = mapped_column(ForeignKey("calculations.id"), nullable=True)
    test_mode: Mapped[bool | None] = mapped_column(nullable=True)
    parts_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    parts_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    parts_quoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parts_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parts_search_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    parts_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parts_complete: Mapped[bool | None] = mapped_column(nullable=True)
    parts_query_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    parts_permission_confirmed: Mapped[bool | None] = mapped_column(nullable=True)
    parts_prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(),
                                                  onupdate=func.current_timestamp())
    user: Mapped[User] = relationship(back_populates="calculations")


engine = create_async_engine(
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    from database.migrations import migrate
    await migrate(engine)


async def close_db() -> None:
    await engine.dispose()
