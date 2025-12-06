from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud, schemas
from ..deps import get_session

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("/by-telegram", response_model=schemas.UserResponse)
async def get_or_create_user(payload: schemas.UserCreateRequest, session: AsyncSession = Depends(get_session)):
    user = await crud.get_or_create_user(session, payload.telegram_id)
    return schemas.UserResponse.model_validate(user.__dict__, from_attributes=True)
