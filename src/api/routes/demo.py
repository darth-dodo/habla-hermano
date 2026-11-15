"""Create a seeded demo account over HTTP, for showing the app."""

import logging

from fastapi import APIRouter, Depends

from src.api.auth import CurrentUserDep
from src.api.rate_limit import rate_limit
from src.api.supabase_client import get_supabase_admin
from src.services.demo_seed import create_demo_account

logger = logging.getLogger(__name__)

router = APIRouter()


# shortcut: any signed-in user may create demo accounts (3 per hour per IP); gate
# it behind an admin role if the app opens to strangers.
@router.post("/demo/seed", dependencies=[Depends(rate_limit(3, 3600))])
def seed_demo(user: CurrentUserDep) -> dict[str, str]:
    """Create a new demo user with four weeks of history and return its login.

    A plain ``def`` so FastAPI runs the blocking Supabase calls in a thread.
    """
    email, password = create_demo_account(get_supabase_admin())
    logger.info("Demo account %s created by user %s", email, user.id)
    return {"email": email, "password": password, "next": "Sign in, then open /progress"}
