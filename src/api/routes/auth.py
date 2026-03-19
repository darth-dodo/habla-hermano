"""Authentication routes for user signup, login, and logout.

Provides endpoints for Supabase authentication with HTMX support.
Uses httponly cookies for secure JWT storage. Stores both access and
refresh tokens to enable transparent token renewal.

Note: Guest users have chat access only with no data persistence.
Progress tracking requires signing up for an account.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from supabase import AuthApiError, Client, create_client

from src.api.config import get_settings
from src.api.cookies import delete_secure_cookie, set_secure_cookie
from src.api.dependencies import SettingsDep, TemplatesDep
from src.api.rate_limit import AUTH_RATE_LIMIT_CALLS, AUTH_RATE_LIMIT_PERIOD, rate_limited

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Cookie configuration
COOKIE_NAME = "sb-access-token"
REFRESH_COOKIE_NAME = "sb-refresh-token"
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
    """Set the access token authentication cookie on the response.

    Deprecated: Prefer set_auth_cookies() which also stores the refresh token.

    Args:
        response: FastAPI response object.
        access_token: JWT access token from Supabase.
    """
    set_secure_cookie(
        response,
        key=COOKIE_NAME,
        value=access_token,
        max_age=COOKIE_MAX_AGE,
    )


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
) -> None:
    """Set authentication cookies (access + refresh) on the response.

    Always sets the access token cookie. If a refresh token is provided,
    also sets the refresh token cookie. Both cookies are httponly and
    secure to prevent client-side script access and transmission over
    plain HTTP.

    Args:
        response: FastAPI response object.
        access_token: JWT access token from Supabase.
        refresh_token: Optional refresh token from Supabase session.
    """
    set_secure_cookie(
        response,
        key=COOKIE_NAME,
        value=access_token,
        max_age=COOKIE_MAX_AGE,
    )
    if refresh_token:
        set_secure_cookie(
            response,
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=COOKIE_MAX_AGE,
        )


def clear_auth_cookie(response: Response) -> None:
    """Clear the authentication cookies from the response.

    Removes both the access token and refresh token cookies.

    Args:
        response: FastAPI response object.
    """
    delete_secure_cookie(response, key=COOKIE_NAME)
    delete_secure_cookie(response, key=REFRESH_COOKIE_NAME)


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
    response = templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


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
    response = templates.TemplateResponse(
        request=request,
        name="auth/signup.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/signup", response_class=HTMLResponse)
@rate_limited(calls=AUTH_RATE_LIMIT_CALLS, period=AUTH_RATE_LIMIT_PERIOD)
async def signup(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
) -> Response:
    """Handle user signup with email and password.

    Creates a new user account via Supabase Auth. On success, sets
    httponly cookies with the JWT access and refresh tokens and redirects
    to the chat page.

    Note: Guest data is not merged on signup. Guests have chat-only access
    without data persistence. Users must sign up to start tracking progress.

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
        response: Response = templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": "Passwords do not match",
                "email": email,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    # Validate password length
    if len(password) < 8:
        response = templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": "Password must be at least 8 characters",
                "email": email,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

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
            response = templates.TemplateResponse(
                request=request,
                name="auth/signup.html",
                context={
                    "error": "Signup failed. Please try again.",
                    "email": email,
                },
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        # Check if email confirmation is required
        if auth_response.session is None:
            # Email confirmation required - show success message
            response = templates.TemplateResponse(
                request=request,
                name="auth/signup.html",
                context={
                    "success": "Please check your email to confirm your account.",
                    "email": email,
                },
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        # Session created - set cookies and redirect
        response = Response(status_code=status.HTTP_200_OK)
        set_auth_cookies(
            response,
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
        )

        # Clear any existing guest session cookie
        delete_secure_cookie(response, key="session_id")

        response.headers["HX-Redirect"] = "/"
        return response

    except AuthApiError as e:
        logger.warning("Signup error: %s", e)
        error_message = str(e)

        # Parse common Supabase errors
        if "already registered" in error_message.lower():
            error_message = "An account with this email already exists"
        elif "invalid email" in error_message.lower():
            error_message = "Please enter a valid email address"

        response = templates.TemplateResponse(
            request=request,
            name="auth/signup.html",
            context={
                "error": error_message,
                "email": email,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response


@router.post("/login", response_class=HTMLResponse)
@rate_limited(calls=AUTH_RATE_LIMIT_CALLS, period=AUTH_RATE_LIMIT_PERIOD)
async def login(
    request: Request,
    templates: TemplatesDep,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    """Handle user login with email and password.

    Authenticates user via Supabase Auth. On success, sets httponly
    cookies with the JWT access and refresh tokens and redirects to
    the chat page.

    Note: Guest data is not merged on login. Guests have chat-only access
    without data persistence. Users must sign up to start tracking progress.

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
            response: Response = templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={
                    "error": "Invalid email or password",
                    "email": email,
                },
            )
            response.headers["Cache-Control"] = "no-store"
            return response

        # Set cookies and redirect via HTMX
        response = Response(status_code=status.HTTP_200_OK)
        set_auth_cookies(
            response,
            access_token=auth_response.session.access_token,
            refresh_token=auth_response.session.refresh_token,
        )

        # Clear any existing guest session cookie
        delete_secure_cookie(response, key="session_id")

        response.headers["HX-Redirect"] = "/"
        return response

    except AuthApiError as e:
        logger.warning("Login error: %s", e)
        error_message = str(e)

        # Parse common Supabase errors
        if "invalid login credentials" in error_message.lower():
            error_message = "Invalid email or password"
        elif "email not confirmed" in error_message.lower():
            error_message = "Please confirm your email address before logging in"

        response = templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "error": error_message,
                "email": email,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response


@router.post("/logout")
async def logout(request: Request, response: Response) -> Response:
    """Log out the current user by invalidating the session and clearing cookies.

    Attempts to sign out server-side via Supabase (invalidating the refresh
    token) before clearing client-side cookies. If server-side sign-out fails,
    cookies are still cleared.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.

    Returns:
        Response: Empty response with HX-Redirect header.
    """
    # Attempt server-side session invalidation
    try:
        access_token = request.cookies.get("sb-access-token")
        if access_token:
            from src.db.client import get_supabase_for_user  # noqa: PLC0415

            client = get_supabase_for_user(access_token)
            client.auth.sign_out()
    except Exception:
        logger.debug("Server-side sign-out failed (token may already be expired)")

    clear_auth_cookie(response)
    response.headers["HX-Redirect"] = "/auth/login"
    response.status_code = status.HTTP_200_OK
    return response


@router.get("/logout")
async def logout_get() -> RedirectResponse:
    """Handle GET request for logout (e.g., direct link).

    Clears the auth cookies and redirects to login page.

    Returns:
        RedirectResponse: Redirect to login page.
    """
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_302_FOUND)
    clear_auth_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Render the forgot password page.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.

    Returns:
        HTMLResponse: Rendered forgot password page.
    """
    response = templates.TemplateResponse(
        request=request,
        name="auth/forgot_password.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/forgot-password", response_class=HTMLResponse)
@rate_limited(calls=AUTH_RATE_LIMIT_CALLS, period=AUTH_RATE_LIMIT_PERIOD)
async def forgot_password(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    email: Annotated[str, Form()],
) -> Response:
    """Handle forgot password request.

    Sends a password reset email via Supabase Auth. Always shows a
    success message regardless of whether the email exists to prevent
    email enumeration attacks.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        email: User's email address.

    Returns:
        Response: Rendered forgot password page with success message.
    """
    redirect_url = str(request.base_url).rstrip("/") + "/auth/reset-password"

    try:
        supabase = get_supabase_client()
        supabase.auth.reset_password_for_email(email, options={"redirect_to": redirect_url})
    except AuthApiError as e:
        # Log the error but don't reveal it to the user
        logger.warning("Password reset request error: %s", e)

    # Always show success to prevent email enumeration
    response: Response = templates.TemplateResponse(
        request=request,
        name="auth/forgot_password.html",
        context={
            "app_name": settings.APP_NAME,
            "success": "If an account exists with that email, you'll receive a password reset link shortly.",
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
) -> HTMLResponse:
    """Render the reset password page.

    This page receives the user after clicking the Supabase recovery
    link. The token exchange happens client-side via JavaScript.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.

    Returns:
        HTMLResponse: Rendered reset password page.
    """
    response = templates.TemplateResponse(
        request=request,
        name="auth/reset_password.html",
        context={
            "app_name": settings.APP_NAME,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/reset-password", response_class=HTMLResponse)
@rate_limited(calls=AUTH_RATE_LIMIT_CALLS, period=AUTH_RATE_LIMIT_PERIOD)
async def reset_password(
    request: Request,
    templates: TemplatesDep,
    settings: SettingsDep,
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    access_token: Annotated[str, Form()] = "",
) -> Response:
    """Handle password reset submission.

    Validates the new password and updates it via a user-scoped
    Supabase client authenticated with the recovery access token.

    Args:
        request: FastAPI request object.
        templates: Jinja2 templates instance.
        settings: Application settings.
        password: New password.
        confirm_password: Password confirmation.
        access_token: Recovery access token from Supabase.

    Returns:
        Response: Redirect to login on success, or error message on failure.
    """
    # Validate access token is present
    if not access_token.strip():
        response: Response = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={
                "app_name": settings.APP_NAME,
                "error": "Invalid or expired reset link. Please request a new one.",
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    # Validate passwords match
    if password != confirm_password:
        response = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={
                "app_name": settings.APP_NAME,
                "error": "Passwords do not match",
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    # Validate password length
    if len(password) < 8:
        response = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={
                "app_name": settings.APP_NAME,
                "error": "Password must be at least 8 characters",
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    try:
        from src.db.client import get_supabase_for_user  # noqa: PLC0415

        client = get_supabase_for_user(access_token)
        client.auth.update_user({"password": password})

        response = Response(status_code=status.HTTP_200_OK)
        response.headers["HX-Redirect"] = "/auth/login"
        return response

    except AuthApiError as e:
        logger.warning("Password reset error: %s", e)
        response = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={
                "app_name": settings.APP_NAME,
                "error": "Failed to reset password. The link may have expired. "
                "Please request a new one.",
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response
