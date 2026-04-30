from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, extract, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.document import Document, DocumentStatus, FileType
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Аналитика"])


@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сводная аналитика по документам текущего пользователя."""

    base = select(Document).where(Document.uploaded_by == current_user.id)

    # Total counts by status
    status_query = (
        select(
            Document.status,
            func.count(Document.id).label("cnt"),
        )
        .where(Document.uploaded_by == current_user.id)
        .group_by(Document.status)
    )
    status_result = await db.execute(status_query)
    status_counts = {row.status.value: row.cnt for row in status_result}
    total = sum(status_counts.values())

    # Counts by file_type (for pie chart)
    type_query = (
        select(
            Document.file_type,
            func.count(Document.id).label("cnt"),
        )
        .where(Document.uploaded_by == current_user.id)
        .group_by(Document.file_type)
    )
    type_result = await db.execute(type_query)
    type_counts = {row.file_type.value: row.cnt for row in type_result}

    # Monthly document counts for last 12 months (for area chart)
    twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)
    monthly_query = (
        select(
            extract("year", Document.created_at).label("year"),
            extract("month", Document.created_at).label("month"),
            func.count(Document.id).label("cnt"),
        )
        .where(
            Document.uploaded_by == current_user.id,
            Document.created_at >= twelve_months_ago,
        )
        .group_by("year", "month")
        .order_by("year", "month")
    )
    monthly_result = await db.execute(monthly_query)

    month_names = [
        "", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
        "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
    ]
    monthly_data = []
    for row in monthly_result:
        monthly_data.append({
            "name": f"{month_names[int(row.month)]} {int(row.year)}",
            "value": row.cnt,
        })

    # Processed vs total by year (for bar chart)
    yearly_query = (
        select(
            extract("year", Document.created_at).label("year"),
            func.count(Document.id).label("total"),
            func.count(
                case(
                    (Document.status.in_([DocumentStatus.PROCESSED, DocumentStatus.VERIFIED]), Document.id),
                )
            ).label("processed"),
        )
        .where(Document.uploaded_by == current_user.id)
        .group_by("year")
        .order_by("year")
    )
    yearly_result = await db.execute(yearly_query)
    yearly_data = []
    for row in yearly_result:
        yearly_data.append({
            "name": str(int(row.year)),
            "Всего": row.total,
            "Обработано": row.processed,
        })

    return {
        "total": total,
        "processed": status_counts.get("processed", 0) + status_counts.get("verified", 0),
        "pending": status_counts.get("uploaded", 0) + status_counts.get("processing", 0),
        "errors": status_counts.get("error", 0),
        "by_status": status_counts,
        "by_type": type_counts,
        "monthly": monthly_data,
        "yearly": yearly_data,
    }
