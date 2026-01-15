from fastapi import APIRouter

from app.api.v1.endpoints.addresses import router as address_router

api_router = APIRouter()
api_router.include_router(address_router)
