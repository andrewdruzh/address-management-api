import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address_validation import ValidationBatch, ValidationItem
from app.schemas.addresses import (
    AddressInputSchema,
    AddressOutputSchema,
    ValidationResultSchema,
    BatchInfoSchema,
    ValidationMessageSchema,
)


class ValidationService:
    """Service for handling address validation operations."""

    def _normalize_address_data(self, address_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize address data by standardizing string values."""
        normalized_data: dict[str, Any] = {}

        for field_name, field_value in address_data.items():
            if isinstance(field_value, str):
                cleaned_value = field_value.strip()

                if field_name == "address_residential_indicator":
                    cleaned_value = cleaned_value.lower()
                    if cleaned_value not in {"unknown", "yes", "no"}:
                        cleaned_value = "unknown"
                    normalized_data[field_name] = cleaned_value
                    continue

                if field_name == "country_code":
                    normalized_data[field_name] = cleaned_value.upper()
                    continue

                if field_name == "email":
                    normalized_data[field_name] = cleaned_value.lower()
                    continue

                normalized_data[field_name] = cleaned_value.upper()
            else:
                normalized_data[field_name] = field_value

        if "address_residential_indicator" not in normalized_data:
            normalized_data["address_residential_indicator"] = "unknown"

        return normalized_data

    def _determine_validation_status(
        self, address: AddressInputSchema
    ) -> tuple[str, list[ValidationMessageSchema]]:
        """Determine validation status and generate messages for an address."""
        validation_messages: list[ValidationMessageSchema] = []

        if address.country_code.upper() == "US" and not address.postal_code:
            validation_messages.append(
                ValidationMessageSchema(
                    code="missing_postal_code",
                    message="postal_code is recommended for US",
                    level="warning",
                )
            )

        return "verified", validation_messages

    async def create_queued_batch(
        self, db_session: AsyncSession, addresses: list[AddressInputSchema]
    ) -> uuid.UUID:
        """Create a new validation batch in queued status."""
        request_payload = [addr.model_dump() for addr in addresses]

        async with db_session.begin():
            new_batch = ValidationBatch(status="queued", request_payload=request_payload)
            db_session.add(new_batch)
            await db_session.flush()

        return new_batch.id

    async def validate_and_store_addresses(
        self,
        db_session: AsyncSession,
        addresses: list[AddressInputSchema],
    ) -> tuple[uuid.UUID, list[ValidationResultSchema]]:
        """Validate addresses synchronously and store results."""
        validation_results: list[ValidationResultSchema] = []
        request_payload = [addr.model_dump() for addr in addresses]

        async with db_session.begin():
            new_batch = ValidationBatch(
                status="completed", request_payload=request_payload
            )
            db_session.add(new_batch)
            await db_session.flush()

            for address_input in addresses:
                original_data = address_input.model_dump()
                normalized_data = self._normalize_address_data(original_data)

                validation_status, validation_messages = (
                    self._determine_validation_status(address_input)
                )
                messages_data = [msg.model_dump() for msg in validation_messages]

                db_session.add(
                    ValidationItem(
                        batch_id=new_batch.id,
                        status=validation_status,
                        original_address=original_data,
                        matched_address=normalized_data,
                        messages=messages_data,
                    )
                )

                original_output = dict(original_data)
                residential_indicator = original_output.get("address_residential_indicator")
                if isinstance(residential_indicator, str):
                    normalized_indicator = residential_indicator.strip().lower()
                    original_output["address_residential_indicator"] = (
                        normalized_indicator
                        if normalized_indicator in {"unknown", "yes", "no"}
                        else "unknown"
                    )
                elif residential_indicator is None:
                    original_output["address_residential_indicator"] = "unknown"

                validation_results.append(
                    ValidationResultSchema(
                        status=validation_status,
                        original_address=AddressOutputSchema.model_validate(
                            original_output
                        ),
                        matched_address=AddressOutputSchema.model_validate(
                            normalized_data
                        ),
                        messages=validation_messages,
                    )
                )

        return new_batch.id, validation_results

    async def process_batch_validation(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> None:
        """Process an existing validation batch asynchronously."""
        async with db_session.begin():
            batch_record = (
                await db_session.execute(
                    select(ValidationBatch)
                    .where(ValidationBatch.id == batch_id)
                    .with_for_update()
                )
            ).scalars().first()

            if batch_record is None:
                return

            existing_item = (
                await db_session.execute(
                    select(ValidationItem.id)
                    .where(ValidationItem.batch_id == batch_id)
                    .limit(1)
                )
            ).scalar_one_or_none()

            if batch_record.status == "completed" and existing_item is not None:
                return

            request_payload = batch_record.request_payload or []
            if not request_payload:
                batch_record.status = "failed"
                return

            batch_record.status = "processing"

            await db_session.execute(
                delete(ValidationItem).where(ValidationItem.batch_id == batch_id)
            )

            address_list = [AddressInputSchema.model_validate(addr) for addr in request_payload]

            for address_input in address_list:
                original_data = address_input.model_dump()
                normalized_data = self._normalize_address_data(original_data)
                validation_status, validation_messages = (
                    self._determine_validation_status(address_input)
                )

                db_session.add(
                    ValidationItem(
                        batch_id=batch_id,
                        status=validation_status,
                        original_address=original_data,
                        matched_address=normalized_data,
                        messages=[msg.model_dump() for msg in validation_messages],
                    )
                )

            batch_record.status = "completed"

    async def retrieve_batch_results(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> list[ValidationResultSchema]:
        """Retrieve validation results for a specific batch."""
        query = (
            select(ValidationItem)
            .where(ValidationItem.batch_id == batch_id)
            .order_by(ValidationItem.created_at)
        )
        result_rows = (await db_session.execute(query)).scalars().all()

        results: list[ValidationResultSchema] = []
        for item in result_rows:
            results.append(
                ValidationResultSchema(
                    status=item.status,
                    original_address=item.original_address,
                    matched_address=item.matched_address,
                    messages=[
                        ValidationMessageSchema.model_validate(msg)
                        for msg in (item.messages or [])
                    ],
                )
            )

        return results

    async def list_validation_batches(
        self,
        db_session: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[BatchInfoSchema]:
        """List validation batches with optional filtering."""
        query = (
            select(
                ValidationBatch,
                func.count(ValidationItem.id).label("items_count"),
            )
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

        result_rows = (await db_session.execute(query)).all()

        return [
            BatchInfoSchema(
                id=batch_record.id,
                status=batch_record.status,
                created_at=batch_record.created_at,
                items_count=int(item_count or 0),
                request_payload=batch_record.request_payload,
            )
            for (batch_record, item_count) in result_rows
        ]

    async def get_batch_info(
        self,
        db_session: AsyncSession,
        batch_id: uuid.UUID,
    ) -> BatchInfoSchema | None:
        """Get information about a specific validation batch."""
        query = (
            select(
                ValidationBatch,
                func.count(ValidationItem.id).label("items_count"),
            )
            .outerjoin(
                ValidationItem, ValidationItem.batch_id == ValidationBatch.id
            )
            .where(ValidationBatch.id == batch_id)
            .group_by(ValidationBatch.id)
        )

        result_row = (await db_session.execute(query)).first()
        if result_row is None:
            return None

        batch_record, item_count = result_row
        return BatchInfoSchema(
            id=batch_record.id,
            status=batch_record.status,
            created_at=batch_record.created_at,
            items_count=int(item_count or 0),
            request_payload=batch_record.request_payload,
        )

    async def remove_batch(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> bool:
        """Delete a validation batch and its items."""
        async with db_session.begin():
            batch_record = await db_session.get(ValidationBatch, batch_id)
            if batch_record is None:
                return False
            await db_session.execute(
                delete(ValidationItem).where(ValidationItem.batch_id == batch_id)
            )
            await db_session.delete(batch_record)
        return True

    async def reset_batch_for_processing(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> bool:
        """Reset a batch to queued status for reprocessing."""
        async with db_session.begin():
            batch_record = (
                await db_session.execute(
                    select(ValidationBatch)
                    .where(ValidationBatch.id == batch_id)
                    .with_for_update()
                )
            ).scalars().first()

            if batch_record is None:
                return False

            if batch_record.status == "processing":
                raise RuntimeError("processing")

            if not batch_record.request_payload:
                batch_record.status = "failed"
                return False

            batch_record.status = "queued"
            await db_session.execute(
                delete(ValidationItem).where(ValidationItem.batch_id == batch_id)
            )

        return True
