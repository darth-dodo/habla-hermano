"""The /demo admin page: allow-listed emails only, demo accounts only."""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth import AuthenticatedUser, get_current_user
from src.services.demo_seed import is_demo_email
from tests.conftest import CSRF_HEADERS

DEMO_ID, REAL_ID = "demo-id", "real-id"


def _user(uid: str, email: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uid, email=email, created_at="2026-11-15T10:00:00", last_sign_in_at=None
    )


@pytest.fixture
def admin() -> MagicMock:
    admin = MagicMock()
    users = {
        DEMO_ID: _user(DEMO_ID, "demo-ab12cd34@example.com"),
        REAL_ID: _user(REAL_ID, "real@x.com"),
    }
    admin.auth.admin.list_users.side_effect = (
        lambda page, per_page: list(users.values()) if page == 1 else []
    )
    admin.auth.admin.get_user_by_id.side_effect = lambda uid: SimpleNamespace(user=users[uid])
    admin.auth.admin.create_user.return_value.user.id = "new-id"
    return admin


def _client(
    admin: MagicMock, email: str | None, allowed: str = "boss@x.com"
) -> Iterator[TestClient]:
    from src.api.main import create_app

    app = create_app()
    if email:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            id="boss", email=email
        )
    with (
        patch("src.api.routes.demo.get_supabase_admin", return_value=admin),
        patch(
            "src.api.routes.demo.get_settings", return_value=MagicMock(DEMO_ADMIN_EMAILS=allowed)
        ),
        TestClient(app, headers=CSRF_HEADERS) as client,
    ):
        yield client


@pytest.fixture
def boss(admin: MagicMock) -> Iterator[TestClient]:
    yield from _client(admin, "Boss@X.com", allowed=" other@x.com, boss@x.com ")


def test_guest_and_unlisted_users_get_nothing(admin: MagicMock) -> None:
    for email, allowed in (
        (None, "boss@x.com"),
        ("someone@x.com", "boss@x.com"),
        ("boss@x.com", ""),
    ):
        for client in _client(admin, email, allowed):
            assert client.get("/demo").status_code in (401, 404)
            assert client.post("/demo/accounts").status_code in (401, 404)
    admin.auth.admin.create_user.assert_not_called()


def test_page_lists_only_demo_accounts(boss: TestClient) -> None:
    page = boss.get("/demo")
    assert page.status_code == 200
    assert "demo-ab12cd34@example.com" in page.text and "real@x.com" not in page.text


def test_create_shows_the_login_once(boss: TestClient, admin: MagicMock) -> None:
    response = boss.post("/demo/accounts")
    sent = admin.auth.admin.create_user.call_args.args[0]
    assert response.status_code == 200
    assert sent["email"] in response.text and sent["password"] in response.text
    assert is_demo_email(sent["email"]) and sent["email_confirm"] is True


def test_reseed_password_and_delete_work_on_demo_accounts(
    boss: TestClient, admin: MagicMock
) -> None:
    assert boss.post(f"/demo/accounts/{DEMO_ID}/reseed").status_code == 200
    assert admin.table.return_value.insert.call_count == 3
    response = boss.post(f"/demo/accounts/{DEMO_ID}/password")
    new_password = admin.auth.admin.update_user_by_id.call_args.args[1]["password"]
    assert new_password in response.text
    assert boss.delete(f"/demo/accounts/{DEMO_ID}").status_code == 200
    admin.auth.admin.delete_user.assert_called_once_with(DEMO_ID)


def test_real_and_unknown_accounts_are_never_touched(boss: TestClient, admin: MagicMock) -> None:
    admin.auth.admin.get_user_by_id.side_effect = lambda uid: (
        SimpleNamespace(user=_user(REAL_ID, "real@x.com"))
        if uid == REAL_ID
        else (_ for _ in ()).throw(KeyError(uid))
    )
    for uid in (REAL_ID, "missing"):
        assert boss.post(f"/demo/accounts/{uid}/reseed").status_code == 404
        assert boss.post(f"/demo/accounts/{uid}/password").status_code == 404
        assert boss.delete(f"/demo/accounts/{uid}").status_code == 404
    admin.auth.admin.delete_user.assert_not_called()
    admin.auth.admin.update_user_by_id.assert_not_called()
    admin.table.assert_not_called()


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("demo-1@example.com", True),
        ("DEMO-1@EXAMPLE.COM", True),
        ("demo@gmail.com", False),
        ("me@example.com", False),
        (None, False),
    ],
)
def test_is_demo_email(email: str | None, expected: bool) -> None:
    assert is_demo_email(email) is expected
