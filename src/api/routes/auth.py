"""Authentication routes for user signup, login, and logout.

Provides endpoints for Supabase authentication with HTMX support.
Uses httponly cookies for secure JWT storage.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import Client, create_client

from src.api.config import get_settings
from src.api.dependencies import SettingsDep, TemplatesDep
from src.services.merge import GuestDataMergeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie configuration
COOKIE_NAME = "sb-access-token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds


def get_supabase_client() -> Client:
    """Create and return a Supabase client instance.

    Returns:
        Client: Configured Supabase client.

    Raises:
        HTTPException: If Supabase is not configured.
    """
    settings = get_settings()

    if not settings.supabase_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured",
        )

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def set_auth_cookie(response: Response, access_token: str) -> None:
    """Set the authentication cookie on the response.

    Args:
        response: FastAPI response object.
        access_token: JWT access token from Supabase.
    """
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,  # Only send over HTTPS
        samesite="lax",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookie from the response.

    Args:
        response: FastAPI response object.
    """
    response.delete_cookie(key=COOKIE_NAME)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Render the login page.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.

    Returns:
        HTMLResponse: Rendered login page.
    """
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Render the signup page.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.

    Returns:
        HTMLResponse: Rendered signup page.
    """
    return templates.TemplateResponse(
        request=request,
        name="auth/signup.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )


@router.post("/signup", response_class=HTMLResponse)
async def signup(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
) -> Response:
    """Handle user signup with email and password.

    Creates a new user account via Supabase Auth. On success, sets
    an httponly cookie with the JWT and redirects to the chat page.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        email: User's email address.
        password: User's password.
        confirm_password: Password confirmation.

    Returns:
        Response: Redirect to chat on success, or error message on failure.
    """
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": "Passwords do not match",
                "email": email,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Validate password length
    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": "Password must be at least 8 characters",
                "email": email,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        supabase = get_supabase_client()
        auth_response = supabase.auth.sign_up(
            {
                "email": email,
                "password": password,
            }
        )

        # Check if signup was successful
        if auth_response.user is None:
            return templates.TemplateResponse(
                request=request,
                name="auth/signup.html",
                context={
                    "error": "Signup failed. Please try again.",
                    "email": email,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Check if email confirmation is required
        if auth_response.session is None:
            # Email confirmation required - show success message
            return templates.TemplateResponse(
                request=request,
                name="auth/signup.html",
                context={
                    "success": "Please check your email to confirm your account.",
                    "email": email,
                },
            )

        # Session created - set cookie and redirect
        response = Response(status_code=status.HTTP_200_OK)
        set_auth_cookie(response, auth_response.session.access_token)

        # Merge guest data if session_id cookie exists (fire-and-forget)
        guest_session_id = request.cookies.get("session_id")
        if guest_session_id and auth_response.user:
            try:
                merge_service = GuestDataMergeService(
                    guest_session_id=guest_session_id,
                    authenticated_user_id=auth_response.user.id,
                )
                result = merge_service.merge_all()
                logger.info("Merged guest data on signup: %s", result)
                response.delete_cookie(key="session_id")
            except Exception:
                logger.exception("Failed to merge guest data on signup")

        response.headers["HX-Redirect"] = "/"
        return response

    except Exception as e:
        logger.exception("Signup error")
        error_message = str(e)

        # Parse common Supabase errors
        if "already registered" in error_message.lower():
            error_message = "An account with this email already exists"
        elif "invalid email" in error_message.lower():
            error_message = "Please enter a valid email address"

        return templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": error_message,
                "email": email,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    """Handle user login with email and password.

    Authenticates user via Supabase Auth. On success, sets an httponly
    cookie with the JWT and redirects to the chat page.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        email: User's email address.
        password: User's password.

    Returns:
        Response: Redirect to chat on success, or error message on failure.
    """
    try:
        supabase = get_supabase_client()
        auth_response = supabase.auth.sign_in_with_password(
            {
                "email": email,
                "password": password,
            }
        )

        if auth_response.session is None:
            return templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={
                    "error": "Invalid email or password",
                    "email": email,
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # Set cookie and redirect via HTMX
        response = Response(status_code=status.HTTP_200_OK)
        set_auth_cookie(response, auth_response.session.access_token)

        # Merge guest data if session_id cookie exists (fire-and-forget)
        guest_session_id = request.cookies.get("session_id")
        if guest_session_id and auth_response.user:
            try:
                merge_service = GuestDataMergeService(
                    guest_session_id=guest_session_id,
                    authenticated_user_id=auth_response.user.id,
                )
                result = merge_service.merge_all()
                logger.info("Merged guest data on login: %s", result)
                response.delete_cookie(key="session_id")
            except Exception:
                logger.exception("Failed to merge guest data on login")

        response.headers["HX-Redirect"] = "/"
        return response

    except Exception as e:
        logger.exception("Login error")
        error_message = str(e)

        # Parse common Supabase errors
        if "invalid login credentials" in error_message.lower():
            error_message = "Invalid email or password"
        elif "email not confirmed" in error_message.lower():
            error_message = "Please confirm your email address before logging in"

        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": error_message,
                "email": email,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


@router.post("/logout")
async def logout(response: Response) -> Response:
    """Log out the current user by clearing the auth cookie.

    Uses HTMX redirect to send user to the login page.

    Args:
        response: FastAPI response object.

    Returns:
        Response: Empty response with HX-Redirect header.
    """
    clear_auth_cookie(response)
    response.headers["HX-Redirect"] = "/auth/login"
    response.status_code = status.HTTP_200_OK
    return response


@router.get("/logout")
async def logout_get() -> RedirectResponse:
    """Handle GET request for logout (e.g., direct link).

    Clears the auth cookie and redirects to login page.

    Returns:
        RedirectResponse: Redirect to login page.
    """
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookie(response)
    return response
