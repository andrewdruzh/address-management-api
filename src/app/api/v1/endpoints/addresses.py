import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.database import get_database_session
from app.models.address_recognition import RecognitionItem
from app.schemas.addresses import (
    AddressInputSchema,
    BatchInfoSchema,
    BatchStatusType,
    PartialAddressSchema,
    RecognitionRequestSchema,
    RecognitionResultSchema,
    ValidationResultSchema,
)
from app.services.address_recognition import RecognitionService
from app.services.address_validation import ValidationService


class AddressEndpoints:
    """API endpoints for address validation and recognition operations."""

    def __init__(self) -> None:
        self.router = APIRouter(tags=["addresses"])
        self.validation_service = ValidationService()
        self.recognition_service = RecognitionService()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Register all route handlers."""
        self.router.post(
            "/v1/addresses/validate",
            response_model=list[ValidationResultSchema],
            responses={
                status.HTTP_202_ACCEPTED: {
                    "description": (
                        "Accepted. Batch queued for background validation (ARQ). "
                        "Response body is empty list. Batch id returned in X-Validation-Batch-Id header."
                    )
                }
            },
        )(self.validate_addresses_endpoint)

        self.router.get(
            "/v1/addresses/validate/{batch_id}",
            response_model=list[ValidationResultSchema],
        )(self.get_validation_results_endpoint)

        self.router.get(
            "/v1/validation-batches",
            response_model=list[BatchInfoSchema],
        )(self.list_validation_batches_endpoint)

        self.router.get(
            "/v1/validation-batches/{batch_id}",
            response_model=BatchInfoSchema,
        )(self.get_validation_batch_endpoint)

        self.router.delete(
            "/v1/validation-batches/{batch_id}",
            status_code=status.HTTP_204_NO_CONTENT,
        )(self.delete_validation_batch_endpoint)

        self.router.post(
            "/v1/validation-batches/{batch_id}/requeue",
            status_code=status.HTTP_202_ACCEPTED,
        )(self.requeue_validation_batch_endpoint)

        self.router.put(
            "/v1/addresses/recognize",
            response_model=list[RecognitionResultSchema],
            responses={
                status.HTTP_202_ACCEPTED: {
                    "description": "Accepted. Recognition queued (ARQ)."
                }
            },
        )(self.recognize_addresses_endpoint)

        self.router.get(
            "/v1/addresses/recognize/{recognition_id}",
            response_model=list[RecognitionResultSchema],
        )(self.get_recognition_results_endpoint)

    async def validate_addresses_endpoint(
        self,
        request: Request,
        response: Response,
        addresses: list[AddressInputSchema],
        async_mode: bool = Query(False, alias="async"),
        db_session: AsyncSession = Depends(get_database_session),
    ) -> list[ValidationResultSchema]:
        """Validate addresses synchronously or queue for async processing."""
        if async_mode:
            batch_id = await self.validation_service.create_queued_batch(
                db_session, addresses
            )
            await request.app.state.redis.enqueue_job(
                "validate_addresses_batch", str(batch_id)
            )

            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["X-Validation-Batch-Id"] = str(batch_id)
            return []

        batch_id, results = await self.validation_service.validate_and_store_addresses(
            db_session, addresses
        )
        response.headers["X-Validation-Batch-Id"] = str(batch_id)
        return results

    async def get_validation_results_endpoint(
        self,
        batch_id: uuid.UUID,
        db_session: AsyncSession = Depends(get_database_session),
    ) -> list[ValidationResultSchema]:
        """Retrieve validation results for a specific batch."""
        results = await self.validation_service.retrieve_batch_results(
            db_session, batch_id
        )
        if not results:
            raise HTTPException(
                status_code=404, detail="batch_id not found or empty"
            )
        return results

    async def list_validation_batches_endpoint(
        self,
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        status_filter: BatchStatusType | None = Query(None, alias="status"),
        db_session: AsyncSession = Depends(get_database_session),
    ) -> list[BatchInfoSchema]:
        """List validation batches with optional filtering."""
        return await self.validation_service.list_validation_batches(
            db_session,
            limit=limit,
            offset=offset,
            status=status_filter,
        )

    async def get_validation_batch_endpoint(
        self,
        batch_id: uuid.UUID,
        db_session: AsyncSession = Depends(get_database_session),
    ) -> BatchInfoSchema:
        """Get information about a specific validation batch."""
        batch_info = await self.validation_service.get_batch_info(
            db_session, batch_id
        )
        if batch_info is None:
            raise HTTPException(status_code=404, detail="batch_id not found")
        return batch_info

    async def delete_validation_batch_endpoint(
        self,
        batch_id: uuid.UUID,
        db_session: AsyncSession = Depends(get_database_session),
    ) -> None:
        """Delete a validation batch and its items."""
        success = await self.validation_service.remove_batch(db_session, batch_id)
        if not success:
            raise HTTPException(status_code=404, detail="batch_id not found")

    async def requeue_validation_batch_endpoint(
        self,
        request: Request,
        batch_id: uuid.UUID,
        db_session: AsyncSession = Depends(get_database_session),
    ) -> None:
        """Reset a validation batch to queued status for reprocessing."""
        try:
            success = await self.validation_service.reset_batch_for_processing(
                db_session, batch_id
            )
        except RuntimeError:
            raise HTTPException(
                status_code=409, detail="batch is processing"
            )

        if not success:
            raise HTTPException(status_code=404, detail="batch_id not found")

        await request.app.state.redis.enqueue_job(
            "validate_addresses_batch", str(batch_id)
        )

    async def recognize_addresses_endpoint(
        self,
        request: Request,
        response: Response,
        payload: list[RecognitionRequestSchema],
        async_mode: bool = Query(False, alias="async"),
        db_session: AsyncSession = Depends(get_database_session),
    ) -> list[RecognitionResultSchema]:
        """Recognize addresses synchronously or queue for async processing."""
        if async_mode:
            recognition_id = (
                await self.recognition_service.create_queued_recognition_batch(
                    db_session, payload
                )
            )
            await request.app.state.redis.enqueue_job(
                "recognize_addresses_batch",
                str(recognition_id),
            )

            response.status_code = status.HTTP_202_ACCEPTED
            response.headers["X-Recognition-Id"] = str(recognition_id)
            return []

        recognition_id, results = (
            await self.recognition_service.recognize_and_store_addresses(
                db_session, payload
            )
        )
        response.headers["X-Recognition-Id"] = str(recognition_id)
        return results

    async def get_recognition_results_endpoint(
        self,
        recognition_id: uuid.UUID,
        db_session: AsyncSession = Depends(get_database_session),
    ) -> list[RecognitionResultSchema]:
        """Retrieve recognition results for a specific batch."""
        query = (
            select(RecognitionItem)
            .where(RecognitionItem.batch_id == recognition_id)
            .order_by(RecognitionItem.created_at)
        )

        result_rows = (await db_session.execute(query)).scalars().all()

        if not result_rows:
            raise HTTPException(
                status_code=404, detail="recognition_id not found or empty"
            )

        results: list[RecognitionResultSchema] = []

        for item in result_rows:
            recognition_data = item.recognized or {}

            results.append(
                RecognitionResultSchema(
                    status="recognized",
                    original_address=PartialAddressSchema.model_validate(
                        recognition_data.get("original_address") or {}
                    ),
                    recognized_address=PartialAddressSchema.model_validate(
                        recognition_data.get("recognized_address") or {}
                    ),
                )
            )

        return results


address_endpoints = AddressEndpoints()
router = address_endpoints.router
