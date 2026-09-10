from fastapi import APIRouter
from app.api.v1.endpoints import health, passport, evisa, aadhaar, face

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(passport.router, tags=["passport"])
api_router.include_router(evisa.router, tags=["evisa"])
api_router.include_router(aadhaar.router, tags=["aadhaar"])
api_router.include_router(face.router, tags=["face"])
