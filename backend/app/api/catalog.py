from fastapi import APIRouter

from app.evaluation import registry
from app.schemas.run import ModelOut, ProfileOut

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/models")
def list_models() -> list[ModelOut]:
    return [ModelOut(alias=m.alias, provider=m.provider, description=m.description) for m in registry.list_models()]


@router.get("/evaluation-profiles")
def list_profiles() -> list[ProfileOut]:
    return [ProfileOut(name=n, description=d) for n, d in registry.EVALUATION_PROFILES.items()]
