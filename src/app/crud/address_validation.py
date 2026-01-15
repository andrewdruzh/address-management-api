import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address_validation import ValidationBatch, ValidationItem


class ValidationCRUD:
    """CRUD operations for validation batches and items."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def create_new_batch(
        self,
        *,
        status: str,
        request_payload: list[dict[str, Any]] | None = None,
    ) -> ValidationBatch:
        """Create a new validation batch."""
        new_batch = ValidationBatch(status=status, request_payload=request_payload)
        self.db_session.add(new_batch)
        await self.db_session.flush()
        return new_batch

    async def fetch_batch_by_id(
        self, batch_id: uuid.UUID
    ) -> ValidationBatch | None:
        """Fetch a validation batch by its ID."""
        return await self.db_session.get(ValidationBatch, batch_id)

    async def list_all_batches(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[tuple[ValidationBatch, int]]:
        """List validation batches with optional status filter."""
        query = (
            select(ValidationBatch, func.count(ValidationItem.id))
            .outerjoin(
                ValidationItem, ValidationItem.batch_id == ValidationBatch.id
            )
            .group_by(ValidationBatch.id)
            .order_by(ValidationBatch.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            query = query.where(ValidationBatch.status == status)

        result_rows = (await self.db_session.execute(query)).all()
        return [(batch_record, int(count)) for (batch_record, count) in result_rows]

    async def fetch_batch_with_item_count(
        self, batch_id: uuid.UUID
    ) -> tuple[ValidationBatch, int] | None:
        """Fetch a validation batch with its item count."""
        query = (
            select(ValidationBatch, func.count(ValidationItem.id))
            .outerjoin(
                ValidationItem, ValidationItem.batch_id == ValidationBatch.id
            )
            .where(ValidationBatch.id == batch_id)
            .group_by(ValidationBatch.id)
        )
        result_row = (await self.db_session.execute(query)).one_or_none()
        if not result_row:
            return None
        batch_record, item_count = result_row
        return batch_record, int(item_count)

    async def remove_batch_items(self, batch_id: uuid.UUID) -> None:
        """Remove all items associated with a validation batch."""
        await self.db_session.execute(
            delete(ValidationItem).where(ValidationItem.batch_id == batch_id)
        )

    async def remove_batch(self, batch_id: uuid.UUID) -> bool:
        """Delete a validation batch."""
        batch_record = await self.db_session.get(ValidationBatch, batch_id)
        if not batch_record:
            return False
        self.db_session.delete(batch_record)
        return True
