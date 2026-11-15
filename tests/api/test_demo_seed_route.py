"""POST /demo/seed: signed-in only, creates a fresh seeded user, returns its login."""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.api.routes import demo


def _client(signed_in: bool) -> TestClient:
    app = FastAPI()
    app.include_router(demo.router)
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id="owner", email="owner@example.com"
        )
    return TestClient(app)


def test_guest_is_refused() -> None:
    assert _client(signed_in=False).post("/demo/seed").status_code == 401


def test_creates_a_new_confirmed_user_and_seeds_only_that_user() -> None:
    admin = MagicMock()
    admin.auth.admin.create_user.return_value.user.id = "new-demo-id"
    with patch.object(demo, "get_supabase_admin", return_value=admin):
        response = _client(signed_in=True).post("/demo/seed")

    assert response.status_code == 200
    body = response.json()
    sent = admin.auth.admin.create_user.call_args.args[0]
    assert body["email"] == sent["email"] and body["password"] == sent["password"]
    assert sent["email_confirm"] is True and len(body["password"]) >= 16
    for call in admin.table.return_value.delete.return_value.eq.call_args_list:
        assert call.args == ("user_id", "new-demo-id")  # never touches the caller's rows
    assert admin.table.return_value.insert.call_count == 3


def test_rate_limited_after_three_calls() -> None:
    admin = MagicMock()
    with patch.object(demo, "get_supabase_admin", return_value=admin):
        client = _client(signed_in=True)
        codes = [client.post("/demo/seed").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
