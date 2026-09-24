from datetime import timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from tests.helpers import DEFAULT_PASSWORD, auth_headers, create_user, login

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)

    response = client.post(
        "/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_login_invalid_password_rejected(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)

    response = client.post(
        "/auth/login", json={"email": user.email, "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_nonexistent_user_rejected(client: TestClient) -> None:
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /auth/refresh
# ---------------------------------------------------------------------------


def test_refresh_rotates_tokens(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    login_body = login(client, user.email)

    response = client.post(
        "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
    )

    assert response.status_code == 200
    body = response.json()
    # The refresh token is a fresh random value on every rotation. The access
    # token is a JWT with second-granularity `exp`; if issued in the same
    # wall-clock second with identical claims it can legitimately be byte-
    # identical to the previous one, so uniqueness isn't asserted here —
    # what matters is that it authenticates successfully, checked below.
    assert body["refresh_token"] != login_body["refresh_token"]

    me_response = client.get("/auth/me", headers=auth_headers(body))
    assert me_response.status_code == 200


def test_refresh_token_is_single_use(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    login_body = login(client, user.email)

    first = client.post("/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert first.status_code == 200

    second = client.post("/auth/refresh", json={"refresh_token": login_body["refresh_token"]})
    assert second.status_code == 401


def test_refresh_rejects_garbage_token(client: TestClient) -> None:
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    login_body = login(client, user.email)

    logout_response = client.post(
        "/auth/logout", json={"refresh_token": login_body["refresh_token"]}
    )
    assert logout_response.status_code == 204

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
    )
    assert refresh_response.status_code == 401


def test_logout_is_idempotent(client: TestClient) -> None:
    response = client.post("/auth/logout", json={"refresh_token": "not-a-real-token"})

    assert response.status_code == 204


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)
    tokens = login(client, user.email)

    response = client.get("/auth/me", headers=auth_headers(tokens))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert "hashed_password" not in body


def test_me_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_me_rejects_expired_token(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session)

    response = login(client, user.email)
    decoded = jwt.decode(
        response["access_token"], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    expired_token = create_access_token(
        subject=decoded["sub"],
        role=decoded["role"],
        token_version=decoded["token_version"],
        expires_delta=timedelta(seconds=-1),
    )

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert me_response.status_code == 401


def test_me_rejects_inactive_user(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, is_active=False)

    token = create_access_token(
        subject=str(user.id), role=user.role.value, token_version=user.token_version
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_me_rejects_stale_token_version(client: TestClient, db_session: Session) -> None:
    """A token signed with an old token_version is rejected — this is what
    lets a password change invalidate every outstanding access token."""
    user = create_user(db_session)
    tokens = login(client, user.email)

    persisted = db_session.query(User).filter(User.id == user.id).one()
    persisted.token_version += 1
    db_session.commit()

    response = client.get("/auth/me", headers=auth_headers(tokens))

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /auth/password
# ---------------------------------------------------------------------------


def test_change_password_succeeds_and_returns_usable_tokens(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    tokens = login(client, user.email)

    response = client.patch(
        "/auth/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-new-strong-password"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens

    # The new access token works.
    me_response = client.get("/auth/me", headers=auth_headers(new_tokens))
    assert me_response.status_code == 200

    # The new password logs in; the old one no longer does.
    assert login(client, user.email, "a-new-strong-password")
    assert (
        client.post(
            "/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
        ).status_code
        == 401
    )


def test_change_password_invalidates_old_access_token(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    tokens = login(client, user.email)

    client.patch(
        "/auth/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-new-strong-password"},
        headers=auth_headers(tokens),
    )

    stale_response = client.get("/auth/me", headers=auth_headers(tokens))
    assert stale_response.status_code == 401


def test_change_password_revokes_existing_refresh_tokens(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    login_body = login(client, user.email)
    tokens = login(client, user.email)  # a second session's tokens

    client.patch(
        "/auth/password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "a-new-strong-password"},
        headers=auth_headers(tokens),
    )

    # The first session's refresh token was revoked by the password change.
    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": login_body["refresh_token"]}
    )
    assert refresh_response.status_code == 401


def test_change_password_rejects_wrong_current_password(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(db_session)
    tokens = login(client, user.email)

    response = client.patch(
        "/auth/password",
        json={"current_password": "wrong-password", "new_password": "a-new-strong-password"},
        headers=auth_headers(tokens),
    )

    assert response.status_code == 401


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.patch(
        "/auth/password",
        json={"current_password": "x", "new_password": "a-new-strong-password"},
    )

    assert response.status_code == 401
