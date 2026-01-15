import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address_recognition import RecognitionBatch, RecognitionItem
from app.schemas.addresses import (
    PartialAddressSchema,
    RecognitionResultSchema,
    RecognitionRequestSchema,
)


class RecognitionService:
    """Service for handling address recognition operations."""

    def _process_address_recognition(
        self, address_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Process and normalize address data for recognition."""
        processed_data: dict[str, Any] = {}

        for field_key, field_value in address_data.items():
            if isinstance(field_value, str):
                cleaned_value = field_value.strip()
                if field_key == "country_code":
                    processed_data[field_key] = cleaned_value.upper()
                elif field_key == "email":
                    processed_data[field_key] = cleaned_value.lower()
                elif field_key == "address_residential_indicator":
                    normalized_indicator = cleaned_value.strip().lower()
                    processed_data[field_key] = (
                        normalized_indicator
                        if normalized_indicator in {"unknown", "yes", "no"}
                        else "unknown"
                    )
                else:
                    processed_data[field_key] = cleaned_value.upper()
            else:
                processed_data[field_key] = field_value

        if (
            "address_residential_indicator" not in processed_data
            or processed_data["address_residential_indicator"] is None
        ):
            processed_data["address_residential_indicator"] = "unknown"

        return processed_data

    async def create_queued_recognition_batch(
        self, db_session: AsyncSession, requests: list[RecognitionRequestSchema]
    ) -> uuid.UUID:
        """Create a new recognition batch in queued status."""
        request_payload = [req.model_dump() for req in requests]
        new_batch = RecognitionBatch(status="queued", request_payload=request_payload)
        db_session.add(new_batch)
        await db_session.flush()
        await db_session.commit()
        return new_batch.id

    async def recognize_and_store_addresses(
        self,
        db_session: AsyncSession,
        requests: list[RecognitionRequestSchema],
    ) -> tuple[uuid.UUID, list[RecognitionResultSchema]]:
        """Recognize addresses synchronously and store results."""
        request_payload = [req.model_dump() for req in requests]
        new_batch = RecognitionBatch(
            status="completed", request_payload=request_payload
        )
        db_session.add(new_batch)
        await db_session.flush()

        recognition_results: list[RecognitionResultSchema] = []

        for recognition_request in requests:
            original_data = (
                recognition_request.address.model_dump()
                if recognition_request.address
                else {}
            )
            recognized_data = self._process_address_recognition(original_data)

            db_session.add(
                RecognitionItem(
                    batch_id=new_batch.id,
                    status="completed",
                    recognized={
                        "original_address": original_data,
                        "recognized_address": recognized_data,
                    },
                )
            )

            recognition_results.append(
                RecognitionResultSchema(
                    original_address=PartialAddressSchema.model_validate(original_data),
                    recognized_address=PartialAddressSchema.model_validate(
                        recognized_data
                    ),
                )
            )

        await db_session.commit()
        return new_batch.id, recognition_results

    async def process_recognition_batch(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> None:
        """Process an existing recognition batch asynchronously."""
        batch_record = await db_session.get(RecognitionBatch, batch_id)
        if batch_record is None:
            return

        if batch_record.status in {"processing", "completed"}:
            return

        request_payload = batch_record.request_payload or []
        if not request_payload:
            batch_record.status = "failed"
            await db_session.commit()
            return

        batch_record.status = "processing"
        await db_session.commit()

        await db_session.execute(
            delete(RecognitionItem).where(RecognitionItem.batch_id == batch_id)
        )

        recognition_requests = [
            RecognitionRequestSchema.model_validate(req) for req in request_payload
        ]
        for recognition_request in recognition_requests:
            original_data = (
                recognition_request.address.model_dump()
                if recognition_request.address
                else {}
            )
            recognized_data = self._process_address_recognition(original_data)
            db_session.add(
                RecognitionItem(
                    batch_id=batch_id,
                    status="completed",
                    recognized={
                        "original_address": original_data,
                        "recognized_address": recognized_data,
                    },
                )
            )

        updated_batch = await db_session.get(RecognitionBatch, batch_id)
        if updated_batch is not None:
            updated_batch.status = "completed"

        await db_session.commit()

    async def retrieve_recognition_results(
        self, db_session: AsyncSession, batch_id: uuid.UUID
    ) -> list[RecognitionResultSchema]:
        """Retrieve recognition results for a specific batch."""
        query = (
            select(RecognitionItem)
            .where(RecognitionItem.batch_id == batch_id)
            .order_by(RecognitionItem.created_at)
        )
        result_rows = (await db_session.execute(query)).scalars().all()

        results: list[RecognitionResultSchema] = []
        for item in result_rows:
            recognition_data = item.recognized or {}
            results.append(
                RecognitionResultSchema(
                    original_address=PartialAddressSchema.model_validate(
                        recognition_data.get("original_address") or {}
                    ),
                    recognized_address=PartialAddressSchema.model_validate(
                        recognition_data.get("recognized_address") or {}
                    ),
                )
            )
        return results
