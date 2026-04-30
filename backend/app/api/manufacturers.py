"""API-эндпоинты для поиска производителей."""
import uuid
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.document import ProcessingTask, DocumentStatus
from app.schemas import (
    ManufacturerSearchRequest,
    ManufacturerSearchResponse,
    ManufacturerInfoRequest,
    ManufacturerInfoResponse,
    ManufacturerResult,
    ManufacturerDocResult,
    ManufacturerExportRequest,
)
from app.services.manufacturer_search import (
    search_manufacturers_by_specs,
    search_manufacturer_info,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/manufacturers", tags=["Поиск производителей"])


@router.post("/search-by-specs", response_model=ManufacturerSearchResponse)
async def search_by_specs(
    request: ManufacturerSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Поиск производителей по характеристикам товара."""
    # Создать задачу обработки для истории
    task = ProcessingTask(
        task_type="manufacturer_search_specs",
        parameters={
            "product_name": request.product_name,
            "characteristics": [c.model_dump() for c in request.characteristics],
            "sources": request.sources,
        },
        created_by=current_user.id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(task)
    await db.flush()

    try:
        raw_results = await search_manufacturers_by_specs(
            product_name=request.product_name,
            characteristics=[c.model_dump() for c in request.characteristics],
            sources=request.sources,
        )

        results = [
            ManufacturerResult(
                name=r.get("name", "Неизвестно"),
                country=r.get("country"),
                website=r.get("website"),
                contacts=r.get("contacts"),
                certificates=r.get("certificates"),
                products=r.get("products"),
                source=r.get("source"),
            )
            for r in raw_results
        ]

        task.status = DocumentStatus.PROCESSED
        task.matching_data = {
            "results_count": len(results),
            "results": [r.model_dump() for r in results],
        }

        return ManufacturerSearchResponse(
            task_id=task.id,
            results=results,
            message=f"Найдено производителей: {len(results)}",
        )

    except Exception as e:
        task.status = DocumentStatus.ERROR
        task.matching_data = {"error": str(e)}
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")


@router.post("/search-by-name", response_model=ManufacturerInfoResponse)
async def search_by_name(
    request: ManufacturerInfoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Поиск производителя и документации по наименованию товара."""
    task = ProcessingTask(
        task_type="manufacturer_search_name",
        parameters={
            "product_name": request.product_name,
            "sources": request.sources,
        },
        created_by=current_user.id,
        status=DocumentStatus.PROCESSING,
    )
    db.add(task)
    await db.flush()

    try:
        raw = await search_manufacturer_info(
            product_name=request.product_name,
            sources=request.sources,
        )

        manufacturers = [
            ManufacturerResult(
                name=m.get("name", "Неизвестно"),
                country=m.get("country"),
                website=m.get("website"),
                contacts=m.get("contacts"),
                is_primary=m.get("is_primary", False),
            )
            for m in raw.get("manufacturers", [])
        ]

        documentation = [
            ManufacturerDocResult(
                title=d.get("title", "Без названия"),
                doc_type=d.get("doc_type"),
                source_url=d.get("source_url"),
                description=d.get("description"),
            )
            for d in raw.get("documentation", [])
        ]

        task.status = DocumentStatus.PROCESSED
        task.matching_data = {
            "manufacturers_count": len(manufacturers),
            "documentation_count": len(documentation),
            "summary": raw.get("summary", ""),
        }

        return ManufacturerInfoResponse(
            task_id=task.id,
            manufacturers=manufacturers,
            documentation=documentation,
            summary=raw.get("summary", ""),
            message=f"Найдено: {len(manufacturers)} производителей, {len(documentation)} документов",
        )

    except Exception as e:
        task.status = DocumentStatus.ERROR
        task.matching_data = {"error": str(e)}
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")


@router.post("/export")
async def export_results(
    request: ManufacturerExportRequest,
    current_user: User = Depends(get_current_user),
):
    """Экспорт результатов поиска производителей в XLSX."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    if not request.results:
        raise HTTPException(status_code=400, detail="Нет данных для экспорта")

    wb = Workbook()
    ws = wb.active
    ws.title = "Производители"

    # Header style
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="003E92", end_color="003E92", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    headers = ["№", "Производитель", "Страна", "Продукция", "Сертификаты", "Контакты", "Сайт", "Источник"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Data rows
    data_alignment = Alignment(vertical="top", wrap_text=True)
    for row_idx, r in enumerate(request.results, 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1).alignment = data_alignment
        ws.cell(row=row_idx, column=2, value=r.name).alignment = data_alignment
        ws.cell(row=row_idx, column=3, value=r.country or "").alignment = data_alignment
        ws.cell(row=row_idx, column=4, value=r.products or "").alignment = data_alignment
        ws.cell(row=row_idx, column=5, value=r.certificates or "").alignment = data_alignment
        ws.cell(row=row_idx, column=6, value=r.contacts or "").alignment = data_alignment
        ws.cell(row=row_idx, column=7, value=r.website or "").alignment = data_alignment
        ws.cell(row=row_idx, column=8, value=r.source or "").alignment = data_alignment

        for col_idx in range(1, 9):
            ws.cell(row=row_idx, column=col_idx).border = thin_border

    # Auto-width
    for col_idx in range(1, 9):
        max_length = max(
            len(str(ws.cell(row=r, column=col_idx).value or ""))
            for r in range(1, len(request.results) + 2)
        )
        ws.column_dimensions[chr(64 + col_idx)].width = min(max(max_length + 2, 10), 40)

    # Save to temp file
    product_slug = (request.product_name or "results").replace(" ", "_")[:30]
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".xlsx", prefix=f"manufacturers_{product_slug}_"
    )
    wb.save(tmp.name)
    tmp.close()

    return FileResponse(
        path=tmp.name,
        filename=f"Производители_{product_slug}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

