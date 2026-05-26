from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("")
async def list_roles():
    """Return server-defined role definitions used by frontends to populate role pickers."""
    # Return roles and default (first) for convenience
    roles = settings.roles
    return {"roles": roles, "default": roles[0]["key"] if roles else None}
