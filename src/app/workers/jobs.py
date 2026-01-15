import uuid

from app.core.db.database import SessionLocal
from app.services.address_recognition import RecognitionService
from app.services.address_validation import ValidationService


async def validate_addresses_batch(ctx, batch_id: str) -> None:
    """Background job to process address validation batch."""
    validation_service = ValidationService()
    batch_uuid = uuid.UUID(batch_id)

    async with SessionLocal() as db_session:
        await validation_service.process_batch_validation(db_session, batch_uuid)


async def recognize_addresses_batch(ctx, batch_id: str) -> None:
    """Background job to process address recognition batch."""
    recognition_service = RecognitionService()
    batch_uuid = uuid.UUID(batch_id)

    async with SessionLocal() as db_session:
        await recognition_service.process_recognition_batch(db_session, batch_uuid)