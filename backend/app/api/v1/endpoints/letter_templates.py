from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session
from app.models.user import User
from app.schemas.letter_template import LetterTemplateCreate, LetterTemplateRead, LetterTemplateUpdate
from app.services.letter_template import LetterTemplateService

router = APIRouter()


@router.get("", response_model=list[LetterTemplateRead])
async def list_letter_templates(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LetterTemplateService(session).list_letters()


@router.get("/{letter_id}", response_model=LetterTemplateRead)
async def get_letter_template(
    letter_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LetterTemplateService(session).get_letter(letter_id)


@router.post("", response_model=LetterTemplateRead, status_code=201)
async def create_letter_template(
    data: LetterTemplateCreate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LetterTemplateService(session).create_letter(data)


@router.patch("/{letter_id}", response_model=LetterTemplateRead)
async def update_letter_template(
    letter_id: str,
    data: LetterTemplateUpdate,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LetterTemplateService(session).update_letter(letter_id, data)


@router.delete("/{letter_id}", response_model=LetterTemplateRead)
async def delete_letter_template(
    letter_id: str,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await LetterTemplateService(session).delete_letter(letter_id)
