import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FileType(str, enum.Enum):
    POSITIONS = "positions"          # Приложение к договору (прайс-лист)
    UPD = "upd"                      # Универсальный передаточный документ
    ACT = "act"                      # Акт оказания услуг
    TEMPLATE = "template"            # Шаблон XLS для заполнения
    GENERATED = "generated"          # Сгенерированный XLS
    PAYMENT_REGISTRY = "payment_registry"    # Реестр платежей
    CONTRACT_REGISTRY = "contract_registry"  # Реестр договоров
    PRIMARY_SUMUP = "primary_sumup"          # Первичный свод (Задача 2, шаг 1)
    REPORT = "report"                # Финальный отчёт (второй свод СМСП, Задача 2, шаг 2)


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"
    VERIFIED = "verified"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UPLOADED
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessingTask(Base):
    """Задача обработки — связывает исходные документы с результатом."""
    __tablename__ = "processing_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # xls_fill, registry_report
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.UPLOADED
    )

    # Входные документы (список UUID)
    source_document_ids: Mapped[list] = mapped_column(JSONB, default=list)
    # Результат (UUID сгенерированного документа)
    result_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    # Данные сопоставления (для проверки пользователем)
    matching_data: Mapped[dict] = mapped_column(JSONB, nullable=True)
    # Параметры обработки
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
