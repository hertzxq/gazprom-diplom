"""
Правила категоризации исключений СМСП.

Используются в классификаторе smsp_classifier для маппинга формулировки
из столбца «Исключение из СМСП» реестра договоров (N) на короткое
наименование категории (авиа/страх/образов/аренда/почта/...).

Перечень редактируется админом через /api/documents/task2/exclusion-rules.
"""
from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SmspExclusionRule(Base):
    __tablename__ = "smsp_exclusion_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    point_letter: Mapped[str] = mapped_column(String(10), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    order_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
