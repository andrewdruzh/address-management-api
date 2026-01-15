import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import DatabaseModel


class ValidationBatch(DatabaseModel):
    """Model representing a batch of address validation requests."""

    __tablename__ = "address_validation_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ValidationItem(DatabaseModel):
    """Model representing a single address validation result within a batch."""

    __tablename__ = "address_validation_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("address_validation_batches.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    original_address: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    matched_address: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
