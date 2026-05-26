from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_roles
from ..models.user import User
from ..schemas.expense_ops import ExpenseCreate, ExpensePostResponse, ExpenseRead
from ..services.expense_service import ExpenseService

router = APIRouter()


@router.get("", response_model=list[ExpenseRead])
async def list_expenses(
	db: AsyncSession = Depends(get_db),
	_: object = Depends(require_roles("super_admin", "admin", "accounts_manager", "viewer")),
) -> list[ExpenseRead]:
	rows = await ExpenseService(db).list_expenses()
	return [ExpenseRead.model_validate(item) for item in rows]


@router.post("", response_model=ExpensePostResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
	payload: ExpenseCreate,
	db: AsyncSession = Depends(get_db),
	user: User = Depends(require_roles("super_admin", "admin", "accounts_manager")),
) -> ExpensePostResponse:
	expense, voucher_no = await ExpenseService(db).create_expense(payload, created_by=user.id)
	return ExpensePostResponse(expense=ExpenseRead.model_validate(expense), voucher_no=voucher_no)
