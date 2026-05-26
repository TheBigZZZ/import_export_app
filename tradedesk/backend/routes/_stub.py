from fastapi import APIRouter, HTTPException, status


def build_stub_router(module_name: str) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def module_health() -> dict[str, str]:
        return {"module": module_name, "status": "stub"}

    @router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def fallback(path: str):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{module_name} endpoint '/{path}' is not implemented yet",
        )

    return router
