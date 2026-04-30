import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole
from app.models.document import FileType, DocumentStatus
from app.models.notification import NotificationType


# ─── Auth ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateAdmin(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ─── Documents ──────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_filename: str
    file_type: FileType
    status: DocumentStatus
    version: int
    file_size: Optional[int]
    metadata_json: Optional[dict]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_type: FileType
    status: DocumentStatus
    message: str


# ─── Processing ─────────────────────────────────────────────────────

class ProcessingRequest(BaseModel):
    positions_document_id: uuid.UUID
    upd_document_id: uuid.UUID
    template_document_id: Optional[uuid.UUID] = None
    document_number: Optional[str] = None
    document_date: Optional[str] = None
    contract_number: Optional[str] = None
    contract_date: Optional[str] = None
    inn_organization: Optional[str] = None
    inn_contractor: Optional[str] = None
    comments: Optional[str] = None
    scenario: Optional[str] = None


class MatchResult(BaseModel):
    upd_row_index: int
    upd_item_name: str
    matched_position_number: Optional[int]
    matched_position_name: Optional[str]
    confidence: float
    needs_review: bool
    quantity: Optional[float] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    total: Optional[float] = None
    highlight_price: bool = False
    highlight_reason: Optional[str] = None


class ProcessingResponse(BaseModel):
    task_id: uuid.UUID
    status: DocumentStatus
    matches: list[MatchResult] = []
    message: str
    result_document_id: Optional[uuid.UUID] = None
    result_document_filename: Optional[str] = None
    document_number: Optional[str] = None
    document_date: Optional[str] = None


class ProcessingTaskResponse(BaseModel):
    id: uuid.UUID
    task_type: str
    status: DocumentStatus
    matching_data: Optional[dict]
    result_document_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Manufacturer Search ────────────────────────────────────────────

class CharacteristicItem(BaseModel):
    key: str
    value: str


class ManufacturerSearchRequest(BaseModel):
    product_name: str
    characteristics: list[CharacteristicItem] = []
    sources: Optional[list[str]] = None


class ManufacturerInfoRequest(BaseModel):
    product_name: str
    sources: Optional[list[str]] = None


class ManufacturerResult(BaseModel):
    name: str
    country: Optional[str] = None
    website: Optional[str] = None
    contacts: Optional[str] = None
    certificates: Optional[str] = None
    products: Optional[str] = None
    source: Optional[str] = None
    is_primary: bool = False


class ManufacturerDocResult(BaseModel):
    title: str
    doc_type: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None


class ManufacturerSearchResponse(BaseModel):
    task_id: uuid.UUID
    results: list[ManufacturerResult] = []
    message: str


class ManufacturerInfoResponse(BaseModel):
    task_id: uuid.UUID
    manufacturers: list[ManufacturerResult] = []
    documentation: list[ManufacturerDocResult] = []
    summary: str = ""
    message: str


# ─── Notifications ──────────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    notification_type: NotificationType
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Manufacturer Export ────────────────────────────────────────────

class ManufacturerExportRequest(BaseModel):
    results: list[ManufacturerResult] = []
    product_name: Optional[str] = None


# ─── Task 2: первичный свод / свод СМСП ──────────────────────────────

class PrimarySumupBuildRequest(BaseModel):
    payment_registry_id: uuid.UUID
    contract_registry_id: uuid.UUID


class PrimarySumupRowDto(BaseModel):
    # Даты — в ISO-формате строкой, чтобы фронт мог сразу печатать.
    date: Optional[str] = None
    contragent: str = ""
    contract_number: str = ""
    contract_date: Optional[str] = None
    contract_sum: Optional[float] = None
    payment_sum: float = 0.0
    smsp_type: str = ""
    smsp_purchase: str = ""
    purchase_method: str = ""
    exclusion_category: str = "нет"
    action_from: Optional[str] = None
    action_to: Optional[str] = None
    is_continuing: str = "нет"
    counter: int = 1
    publication: str = "да"
    payments_count: int = 0
    has_contract_match: bool = False


class PrimarySumupResponse(BaseModel):
    task_id: uuid.UUID
    document_id: uuid.UUID
    rows: list[PrimarySumupRowDto] = []
    rows_total: int = 0
    rows_unmatched: int = 0
    message: str


class PrimarySumupUpdateRequest(BaseModel):
    rows: list[PrimarySumupRowDto]


class FinalSummaryMetric(BaseModel):
    label: str
    total_sum: float
    count: Optional[int] = None


class FinalSummaryRequest(BaseModel):
    primary_sumup_id: uuid.UUID


class FinalSummaryResponse(BaseModel):
    document_id: uuid.UUID
    sheets: dict[str, list[FinalSummaryMetric]] = {}
    message: str


class SmspExclusionRuleDto(BaseModel):
    id: Optional[int] = None
    category: str
    keywords: list[str] = []
    point_letter: Optional[str] = None
    enabled: bool = True
    order_idx: int = 100


class SmspExclusionRulesUpdate(BaseModel):
    rules: list[SmspExclusionRuleDto]

