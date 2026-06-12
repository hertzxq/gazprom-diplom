import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.document import Document, FileType, DocumentStatus, ProcessingTask
from app.models.notification import NotificationType
from app.models.smsp_rules import SmspExclusionRule
from app.services.notifier import add_notification
from app.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    ProcessingRequest,
    ProcessingResponse,
    PrimarySumupBuildRequest,
    PrimarySumupResponse,
    PrimarySumupRowDto,
    PrimarySumupUpdateRequest,
    FinalSummaryRequest,
    FinalSummaryResponse,
    FinalSummaryMetric,
    SmspExclusionRuleDto,
    SmspExclusionRulesUpdate,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/documents", tags=["Документы"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    file_type: FileType = Form(...),
    metadata: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загрузка документа."""
    import json

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Имя файла не задано")

    # Validate file extension
    allowed_extensions = {".pdf", ".xls", ".xlsx"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый формат файла: {file_ext}. Допустимые: {', '.join(allowed_extensions)}",
        )

    # Реестры Задачи 2 парсятся только из Excel — PDF отклоняем сразу,
    # иначе ошибка всплыла бы 500-кой на этапе построения свода.
    if file_type in {FileType.PAYMENT_REGISTRY, FileType.CONTRACT_REGISTRY} and file_ext == ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Реестры платежей и договоров принимаются только в форматах XLS/XLSX",
        )

    # Create upload directory
    upload_dir = settings.UPLOAD_DIR / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file with unique name
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = upload_dir / unique_filename

    content = await file.read()
    max_size = 50 * 1024 * 1024  # синхронно с подсказкой в UI и лимитом nginx
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл превышает максимальный размер 50 МБ",
        )

    with open(file_path, "wb") as f:
        f.write(content)

    # Parse metadata
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}

    # Create DB record
    doc = Document(
        filename=unique_filename,
        original_filename=file.filename,
        file_type=file_type,
        file_path=str(file_path),
        mime_type=file.content_type,
        file_size=len(content),
        metadata_json=meta,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    return DocumentUploadResponse(
        id=doc.id,
        filename=file.filename,
        file_type=doc.file_type,
        status=doc.status,
        message="Файл успешно загружен",
    )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    file_type: FileType | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список документов текущего пользователя."""
    query = select(Document).where(Document.uploaded_by == current_user.id)
    if file_type:
        query = query.where(Document.file_type == file_type)
    query = query.order_by(desc(Document.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить информацию о документе."""
    return await _get_doc(db, document_id, current_user)


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Скачать файл документа."""
    doc = await _get_doc(db, document_id, current_user)

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=str(file_path),
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.post("/process", response_model=ProcessingResponse)
async def process_documents(
    request: ProcessingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запуск обработки: сопоставление позиций и генерация XLS."""
    from app.services.file_parser import parse_document
    from app.services.matcher import match_positions
    from app.services.xls_generator import generate_filled_template

    # Load source documents
    positions_doc = await _get_doc(db, request.positions_document_id, current_user)
    upd_doc = await _get_doc(db, request.upd_document_id, current_user)
    template_doc = None

    if positions_doc.file_type != FileType.POSITIONS:
        raise HTTPException(status_code=400, detail="Файл позиций должен иметь тип positions")
    if upd_doc.file_type not in {FileType.UPD, FileType.ACT}:
        raise HTTPException(status_code=400, detail="Второй файл должен иметь тип upd или act")

    if request.template_document_id:
        template_doc = await _get_doc(db, request.template_document_id, current_user)
        if template_doc.file_type != FileType.TEMPLATE:
            raise HTTPException(status_code=400, detail="Шаблон должен иметь тип template")

    # Create processing task
    task = ProcessingTask(
        task_type="xls_fill",
        source_document_ids=[str(positions_doc.id), str(upd_doc.id)],
        parameters={
            "document_number": request.document_number,
            "document_date": request.document_date,
            "contract_number": request.contract_number,
            "contract_date": request.contract_date,
            "inn_organization": request.inn_organization,
            "inn_contractor": request.inn_contractor,
            "comments": request.comments,
            "template_document_id": str(template_doc.id) if template_doc else None,
            "scenario": request.scenario,
            "use_llm": request.use_llm,
        },
        created_by=current_user.id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(task)
    await db.flush()

    try:
        # Parse files
        positions_data = parse_document(positions_doc.file_path)
        upd_data = parse_document(upd_doc.file_path)

        # Match positions (scenario из формы перевешивает file_type, если задан)
        matches = await match_positions(
            positions_data,
            upd_data,
            source_file_type=upd_doc.file_type.value,
            scenario=request.scenario,
            use_llm=request.use_llm,
        )

        document_number = request.document_number or upd_data.metadata.get("document_number")
        document_date = request.document_date or upd_data.metadata.get("document_date")
        version = await _get_next_generated_version(
            db=db,
            current_user=current_user,
            positions_document=positions_doc,
            upd_document=upd_doc,
            template_document=template_doc,
        )

        # Generate filled XLS
        generated_path = await generate_filled_template(
            matches=matches,
            template_path=template_doc.file_path if template_doc else None,
            task_id=f"{task.id}_v{version}",
            doc_number=document_number or "",
            doc_date=document_date or "",
        )

        # Save generated document
        generated_filename = _build_generated_filename(
            upd_doc=upd_doc,
            version=version,
        )
        gen_doc = Document(
            filename=Path(generated_path).name,
            original_filename=generated_filename,
            file_type=FileType.GENERATED,
            file_path=generated_path,
            status=DocumentStatus.PROCESSED,
            version=version,
            metadata_json={
                "source_document_ids": [str(positions_doc.id), str(upd_doc.id)],
                "template_document_id": str(template_doc.id) if template_doc else None,
                "document_number": document_number,
                "document_date": document_date,
                "comments": request.comments,
            },
            uploaded_by=current_user.id,
        )
        db.add(gen_doc)
        await db.flush()

        task.status = DocumentStatus.PROCESSED
        task.result_document_id = gen_doc.id
        task.matching_data = {
            "matches": [m.model_dump() for m in matches],
            "total_matched": sum(1 for m in matches if not m.needs_review),
            "needs_review": sum(1 for m in matches if m.needs_review),
            "document_number": document_number,
            "document_date": document_date,
            "generated_document_id": str(gen_doc.id),
            "generated_document_version": version,
        }

        success_msg = (
            "Обработка завершена. "
            f"Сопоставлено: {task.matching_data['total_matched']}, "
            f"на проверку: {task.matching_data['needs_review']}. "
            f"Сформирована версия {version}."
        )

        # Create success notification (best-effort)
        add_notification(
            db,
            user_id=current_user.id,
            title="Обработка завершена",
            message=success_msg,
            notification_type=NotificationType.SUCCESS,
        )

        return ProcessingResponse(
            task_id=task.id,
            status=task.status,
            matches=matches,
            message=success_msg,
            result_document_id=gen_doc.id,
            result_document_filename=gen_doc.original_filename,
            document_number=document_number,
            document_date=document_date,
        )

    except Exception as e:
        task.status = DocumentStatus.ERROR
        task.matching_data = {"error": str(e)}

        # Create error notification (best-effort)
        add_notification(
            db,
            user_id=current_user.id,
            title="Ошибка обработки",
            message=f"Ошибка при обработке документов: {str(e)}",
            notification_type=NotificationType.ERROR,
        )

        # Коммитим явно: после raise зависимость get_db делает rollback,
        # и без коммита ERROR-задача с уведомлением не попали бы в БД.
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")


async def _get_doc(db: AsyncSession, doc_id: uuid.UUID, current_user: User) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Документ {doc_id} не найден")
    if current_user.role != UserRole.ADMIN and doc.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к документу")
    return doc


async def _get_next_generated_version(
    db: AsyncSession,
    current_user: User,
    positions_document: Document,
    upd_document: Document,
    template_document: Document | None,
) -> int:
    result = await db.execute(
        select(Document)
        .where(
            Document.file_type == FileType.GENERATED,
            Document.uploaded_by == current_user.id,
        )
        .order_by(desc(Document.created_at))
    )

    source_signature = {
        "source_document_ids": [str(positions_document.id), str(upd_document.id)],
        "template_document_id": str(template_document.id) if template_document else None,
    }

    next_version = 1
    for document in result.scalars():
        metadata = document.metadata_json or {}
        if (
            metadata.get("source_document_ids") == source_signature["source_document_ids"]
            and metadata.get("template_document_id") == source_signature["template_document_id"]
        ):
            next_version = max(next_version, (document.version or 1) + 1)

    return next_version


def _build_generated_filename(upd_doc: Document, version: int) -> str:
    stem = Path(upd_doc.original_filename).stem
    return f"{stem}_filled_v{version}.xlsx"


# ─── Task 2: первичный свод / итоговый свод СМСП ───────────────────────


@router.post("/task2/primary-sumup", response_model=PrimarySumupResponse)
async def build_task2_primary_sumup(
    request: PrimarySumupBuildRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Шаг 1 Задачи 2: построить первичный свод.

    Читает реестры платежей и договоров, агрегирует платежи по договорам,
    подтягивает реквизиты договоров, классифицирует «Исключение из СМСП»,
    сохраняет xlsx как Document(PRIMARY_SUMUP) и возвращает строки для
    preview/редактирования на фронте.
    """
    from app.services.registry_parser import parse_payment_registry, parse_contract_registry
    from app.services.primary_sumup import build_primary_sumup, generate_primary_sumup_xlsx
    from app.services.smsp_classifier import ClassifierRule

    payment_doc = await _get_doc(db, request.payment_registry_id, current_user)
    contract_doc = await _get_doc(db, request.contract_registry_id, current_user)

    if payment_doc.file_type != FileType.PAYMENT_REGISTRY:
        raise HTTPException(status_code=400, detail="Первый документ должен иметь тип payment_registry")
    if contract_doc.file_type != FileType.CONTRACT_REGISTRY:
        raise HTTPException(status_code=400, detail="Второй документ должен иметь тип contract_registry")

    # Правила классификации — из БД.
    rules_result = await db.execute(
        select(SmspExclusionRule).order_by(SmspExclusionRule.order_idx)
    )
    db_rules = rules_result.scalars().all()
    rules = [
        ClassifierRule(
            category=r.category,
            keywords=r.keywords or [],
            point_letter=r.point_letter,
            order_idx=r.order_idx,
            enabled=r.enabled,
        )
        for r in db_rules
    ]

    task = ProcessingTask(
        task_type="smsp_primary_sumup",
        source_document_ids=[str(payment_doc.id), str(contract_doc.id)],
        parameters={
            "date_from": request.date_from.isoformat() if request.date_from else None,
            "date_to": request.date_to.isoformat() if request.date_to else None,
            "min_amount": request.min_amount,
        },
        created_by=current_user.id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(task)
    await db.flush()

    try:
        payments = parse_payment_registry(payment_doc.file_path)
        contracts = parse_contract_registry(contract_doc.file_path)
        sumup_rows = build_primary_sumup(
            payments,
            contracts,
            rules,
            date_from=request.date_from,
            date_to=request.date_to,
            min_amount=request.min_amount,
        )

        out_path = generate_primary_sumup_xlsx(sumup_rows, str(task.id))

        gen_doc = Document(
            filename=Path(out_path).name,
            original_filename="Первичный свод.xlsx",
            file_type=FileType.PRIMARY_SUMUP,
            file_path=out_path,
            status=DocumentStatus.PROCESSED,
            version=1,
            metadata_json={
                "task_id": str(task.id),
                "payment_registry_id": str(payment_doc.id),
                "contract_registry_id": str(contract_doc.id),
                "rows_total": len(sumup_rows),
                "rows_unmatched": sum(1 for r in sumup_rows if not r.has_contract_match),
            },
            uploaded_by=current_user.id,
        )
        db.add(gen_doc)
        await db.flush()

        task.status = DocumentStatus.PROCESSED
        task.result_document_id = gen_doc.id
        task.matching_data = {"rows": [r.to_dict() for r in sumup_rows]}

        rows_dto = [PrimarySumupRowDto(**r.to_dict()) for r in sumup_rows]
        msg = (
            f"Первичный свод построен: {len(sumup_rows)} строк, "
            f"{sum(1 for r in sumup_rows if r.has_contract_match)} сопоставлено с реестром договоров."
        )

        add_notification(
            db,
            user_id=current_user.id,
            title="Первичный свод построен",
            message=msg,
            notification_type=NotificationType.SUCCESS,
        )

        return PrimarySumupResponse(
            task_id=task.id,
            document_id=gen_doc.id,
            rows=rows_dto,
            rows_total=len(sumup_rows),
            rows_unmatched=sum(1 for r in sumup_rows if not r.has_contract_match),
            message=msg,
        )

    except Exception as e:
        task.status = DocumentStatus.ERROR
        task.matching_data = {"error": str(e)}
        # Явный коммит — иначе get_db откатит ERROR-статус задачи (см. /process).
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Ошибка построения первичного свода: {str(e)}")


@router.put("/task2/primary-sumup/{task_id}", response_model=PrimarySumupResponse)
async def update_task2_primary_sumup(
    task_id: uuid.UUID,
    request: PrimarySumupUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Шаг 1.5: сохраняет правки пользователя и перегенерирует xlsx первичного свода."""
    from app.services.primary_sumup import SumupRow, generate_primary_sumup_xlsx
    from datetime import date

    task_result = await db.execute(select(ProcessingTask).where(ProcessingTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if current_user.role != UserRole.ADMIN and task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if task.result_document_id is None:
        raise HTTPException(status_code=400, detail="У задачи нет результирующего документа")

    doc_result = await db.execute(select(Document).where(Document.id == task.result_document_id))
    doc = doc_result.scalar_one_or_none()
    if doc is None or doc.file_type != FileType.PRIMARY_SUMUP:
        raise HTTPException(status_code=404, detail="Документ первичного свода не найден")

    def _parse_date(s: Optional[str]) -> Optional[date]:
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    sumup_rows: list[SumupRow] = []
    for dto in request.rows:
        sumup_rows.append(SumupRow(
            date=_parse_date(dto.date),
            contragent=dto.contragent,
            contract_number=dto.contract_number,
            contract_date=_parse_date(dto.contract_date),
            contract_sum=dto.contract_sum,
            payment_sum=dto.payment_sum,
            smsp_type=dto.smsp_type,
            smsp_purchase=dto.smsp_purchase,
            purchase_method=dto.purchase_method,
            exclusion_category=dto.exclusion_category,
            action_from=_parse_date(dto.action_from),
            action_to=_parse_date(dto.action_to),
            is_continuing=dto.is_continuing,
            counter=dto.counter,
            publication=dto.publication,
            payments_count=dto.payments_count,
            has_contract_match=dto.has_contract_match,
        ))

    out_path = generate_primary_sumup_xlsx(sumup_rows, str(task.id))
    doc.file_path = out_path
    doc.filename = Path(out_path).name
    meta = dict(doc.metadata_json or {})
    meta.update({
        "rows_total": len(sumup_rows),
        "edited": True,
    })
    doc.metadata_json = meta

    task.matching_data = {"rows": [r.to_dict() for r in sumup_rows]}

    return PrimarySumupResponse(
        task_id=task.id,
        document_id=doc.id,
        rows=[PrimarySumupRowDto(**r.to_dict()) for r in sumup_rows],
        rows_total=len(sumup_rows),
        rows_unmatched=sum(1 for r in sumup_rows if not r.has_contract_match),
        message="Первичный свод обновлён",
    )


@router.post("/task2/final-summary", response_model=FinalSummaryResponse)
async def build_task2_final_summary(
    request: FinalSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Шаг 2 Задачи 2: строит итоговый свод СМСП (3 вкладки) из первичного свода."""
    from app.services.smsp_summary import generate_final_summary_xlsx, compute_final_summary
    from app.services.primary_sumup import SumupRow
    from datetime import date

    doc = await _get_doc(db, request.primary_sumup_id, current_user)
    if doc.file_type != FileType.PRIMARY_SUMUP:
        raise HTTPException(status_code=400, detail="Документ должен быть первичным сводом")

    # Источник строк — matching_data исходной задачи.
    task_result = await db.execute(
        select(ProcessingTask).where(ProcessingTask.result_document_id == doc.id)
    )
    task = task_result.scalars().first()
    if task is None or not task.matching_data:
        raise HTTPException(status_code=400, detail="Не найдены данные первичного свода")

    def _parse_date(s):
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    sumup_rows: list[SumupRow] = []
    for d in task.matching_data.get("rows", []):
        sumup_rows.append(SumupRow(
            date=_parse_date(d.get("date")),
            contragent=d.get("contragent", ""),
            contract_number=d.get("contract_number", ""),
            contract_date=_parse_date(d.get("contract_date")),
            contract_sum=d.get("contract_sum"),
            payment_sum=d.get("payment_sum", 0.0),
            smsp_type=d.get("smsp_type", ""),
            smsp_purchase=d.get("smsp_purchase", ""),
            purchase_method=d.get("purchase_method", ""),
            exclusion_category=d.get("exclusion_category", "нет"),
            action_from=_parse_date(d.get("action_from")),
            action_to=_parse_date(d.get("action_to")),
            is_continuing=d.get("is_continuing", "нет"),
            counter=d.get("counter", 1),
            publication=d.get("publication", "да"),
            payments_count=d.get("payments_count", 0),
            has_contract_match=d.get("has_contract_match", False),
        ))

    try:
        out_path = generate_final_summary_xlsx(sumup_rows, str(doc.id))
        preview = compute_final_summary(sumup_rows)
    except Exception as e:
        # Единообразно с /process и /task2/primary-sumup: русскоязычный detail
        # вместо голого Internal Server Error.
        raise HTTPException(status_code=500, detail=f"Ошибка построения итогового свода: {str(e)}")

    report_doc = Document(
        filename=Path(out_path).name,
        original_filename="Второй свод_обобщение.xlsx",
        file_type=FileType.REPORT,
        file_path=out_path,
        status=DocumentStatus.PROCESSED,
        version=1,
        metadata_json={
            "primary_sumup_id": str(doc.id),
        },
        uploaded_by=current_user.id,
    )
    db.add(report_doc)
    await db.flush()

    final_task = ProcessingTask(
        task_type="smsp_final_summary",
        source_document_ids=[str(doc.id)],
        result_document_id=report_doc.id,
        parameters={},
        created_by=current_user.id,
        status=DocumentStatus.PROCESSED,
    )
    db.add(final_task)

    add_notification(
        db,
        user_id=current_user.id,
        title="Итоговый свод СМСП готов",
        message=f"Сформирован файл «Второй свод_обобщение.xlsx» ({len(sumup_rows)} строк в источнике).",
        notification_type=NotificationType.SUCCESS,
    )

    sheets_dto = {
        name: [FinalSummaryMetric(**m) for m in metrics]
        for name, metrics in preview.items()
    }

    return FinalSummaryResponse(
        document_id=report_doc.id,
        sheets=sheets_dto,
        message="Итоговый свод сформирован",
    )


# ─── Правила категоризации исключений СМСП (admin only) ────────────────


@router.get("/task2/exclusion-rules", response_model=list[SmspExclusionRuleDto])
async def list_exclusion_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список правил отнесения к категориям исключений. Доступно всем авторизованным."""
    result = await db.execute(
        select(SmspExclusionRule).order_by(SmspExclusionRule.order_idx, SmspExclusionRule.id)
    )
    items = result.scalars().all()
    return [
        SmspExclusionRuleDto(
            id=r.id,
            category=r.category,
            keywords=r.keywords or [],
            point_letter=r.point_letter,
            enabled=r.enabled,
            order_idx=r.order_idx,
        )
        for r in items
    ]


@router.put("/task2/exclusion-rules", response_model=list[SmspExclusionRuleDto])
async def update_exclusion_rules(
    payload: SmspExclusionRulesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Полная замена набора правил. Только admin.

    Фронт шлёт весь список — бэк удаляет удалённые, обновляет существующие,
    добавляет новые. Это проще, чем дифф, и подходит для небольших таблиц.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Только администратор может менять правила")

    # Загрузим текущие правила в словарь по id.
    current_result = await db.execute(select(SmspExclusionRule))
    current = {r.id: r for r in current_result.scalars().all()}

    incoming_ids = {r.id for r in payload.rules if r.id is not None}
    # Удаляем те, чей id пропал.
    for rid, rule in list(current.items()):
        if rid not in incoming_ids:
            await db.delete(rule)

    # Обновляем / вставляем.
    for dto in payload.rules:
        if dto.id is not None and dto.id in current:
            rule = current[dto.id]
            rule.category = dto.category
            rule.keywords = dto.keywords
            rule.point_letter = dto.point_letter
            rule.enabled = dto.enabled
            rule.order_idx = dto.order_idx
        else:
            db.add(SmspExclusionRule(
                category=dto.category,
                keywords=dto.keywords,
                point_letter=dto.point_letter,
                enabled=dto.enabled,
                order_idx=dto.order_idx,
            ))

    await db.flush()
    return await list_exclusion_rules(db, current_user)
