from fastapi import APIRouter

from app.api.routes import auth, body_measurements, mcp, routines, system, user, workouts


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(user.router)
api_router.include_router(workouts.router)
api_router.include_router(routines.router)
api_router.include_router(body_measurements.router)
api_router.include_router(mcp.router)
api_router.include_router(system.router)
