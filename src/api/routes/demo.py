"""Demo account admin page: create, reseed, re-password and delete demo users.

Only emails listed in DEMO_ADMIN_EMAILS can open it; everyone else gets 404,
so the page does not reveal it exists. Actions only ever touch accounts whose
email matches the demo pattern (see is_demo_email), never real users.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.auth import AuthenticatedUser, CurrentUserDep
from src.api.dependencies import TemplatesDep
from src.api.supabase_client import get_supabase_admin
from src.config import get_settings
from src.services.demo_seed import (
    create_demo_account,
    delete_demo_account,
    get_demo_email,
    list_demo_accounts,
    new_demo_password,
    seed_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["demo"])


def require_demo_admin(user: CurrentUserDep) -> AuthenticatedUser:
    """Allow only the emails in DEMO_ADMIN_EMAILS; 404 for everyone else."""
    allowed = {e.strip().lower() for e in get_settings().DEMO_ADMIN_EMAILS.split(",") if e.strip()}
    if (user.email or "").lower() not in allowed:
        raise HTTPException(status_code=404)
    return user


DemoAdminDep = Annotated[AuthenticatedUser, Depends(require_demo_admin)]


def _panel(request: Request, templates: Jinja2Templates, **context: Any) -> HTMLResponse:
    accounts = list_demo_accounts(get_supabase_admin())
    return templates.TemplateResponse(
        request=request,
        name="partials/demo_accounts.html",
        context={"accounts": accounts, **context},
    )


def _demo_email_or_404(admin: Any, user_id: str) -> str:
    try:
        return get_demo_email(admin, user_id)
    except LookupError:
        raise HTTPException(status_code=404) from None


# Plain ``def`` routes: FastAPI runs the blocking Supabase calls in a thread.
@router.get("", response_class=HTMLResponse)
def demo_page(request: Request, templates: TemplatesDep, user: DemoAdminDep) -> HTMLResponse:
    """The admin page with the list of demo accounts."""
    accounts = list_demo_accounts(get_supabase_admin())
    return templates.TemplateResponse(
        request=request, name="demo.html", context={"user": user, "accounts": accounts}
    )


@router.post("/accounts", response_class=HTMLResponse)
def create_account(request: Request, templates: TemplatesDep, user: DemoAdminDep) -> HTMLResponse:
    """Create a seeded demo account and show its login once."""
    email, password = create_demo_account(get_supabase_admin())
    logger.info("Demo account %s created by %s", email, user.id)
    return _panel(request, templates, creds={"email": email, "password": password})


@router.post("/accounts/{user_id}/reseed", response_class=HTMLResponse)
def reseed_account(
    user_id: str, request: Request, templates: TemplatesDep, user: DemoAdminDep
) -> HTMLResponse:
    """Replace the account's history with fresh data, so the streak ends today."""
    admin = get_supabase_admin()
    email = _demo_email_or_404(admin, user_id)
    seed_user(admin, user_id)
    logger.info("Demo account %s reseeded by %s", email, user.id)
    return _panel(request, templates, notice=f"Reseeded {email}.")


@router.post("/accounts/{user_id}/password", response_class=HTMLResponse)
def reset_password(
    user_id: str, request: Request, templates: TemplatesDep, user: DemoAdminDep
) -> HTMLResponse:
    """Set a new password and show it once."""
    admin = get_supabase_admin()
    email = _demo_email_or_404(admin, user_id)
    password = new_demo_password(admin, user_id)
    logger.info("Demo account %s password reset by %s", email, user.id)
    return _panel(request, templates, creds={"email": email, "password": password})


@router.delete("/accounts/{user_id}", response_class=HTMLResponse)
def delete_account(
    user_id: str, request: Request, templates: TemplatesDep, user: DemoAdminDep
) -> HTMLResponse:
    """Delete the demo account and all its data."""
    admin = get_supabase_admin()
    email = _demo_email_or_404(admin, user_id)
    delete_demo_account(admin, user_id)
    logger.info("Demo account %s deleted by %s", email, user.id)
    return _panel(request, templates, notice=f"Deleted {email}.")
