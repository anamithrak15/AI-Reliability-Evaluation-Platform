import re

import pytest
from sqlalchemy import select

from app.auth import tokens
from app.core.config import Settings, assert_safe_for_environment, get_settings
from app.models import User
from tests.conftest import PASSWORD
from tests.test_auth import AUTH, login, register

NEW_PASSWORD = "a completely different passphrase"


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.mailer.send", sent.append)
    return sent


def token_in(mail) -> str:
    return re.search(r"token=([\w.-]+)", mail.body).group(1)


def test_registration_sends_a_verification_link_and_verifying_marks_the_account(
    anonymous_client, outbox
):
    body = register(anonymous_client).json()
    assert body["email_verified_at"] is None
    assert [m.to for m in outbox] == ["new@example.com"]

    resp = anonymous_client.post(f"{AUTH}/verify-email", json={"token": token_in(outbox[0])})
    assert resp.status_code == 200 and resp.json()["email_verified_at"] is not None
    assert anonymous_client.get(f"{AUTH}/me").json()["email_verified_at"] is not None


def test_verification_link_rejects_garbage_and_other_purposes(anonymous_client, outbox, session_factory):
    register(anonymous_client)
    assert anonymous_client.post(f"{AUTH}/verify-email", json={"token": "nope"}).status_code == 400
    with session_factory() as s:
        user = s.scalar(select(User))
        reset_token = tokens.issue_action_token(user, "reset", 30)
    resp = anonymous_client.post(f"{AUTH}/verify-email", json={"token": reset_token})
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_token"


def test_expired_verification_link_is_rejected(anonymous_client, outbox, session_factory):
    register(anonymous_client)
    with session_factory() as s:
        expired = tokens.issue_action_token(s.scalar(select(User)), "verify", -1)
    assert anonymous_client.post(f"{AUTH}/verify-email", json={"token": expired}).status_code == 400


def test_data_routes_are_blocked_until_verified_when_required(anonymous_client, outbox, monkeypatch):
    monkeypatch.setattr(get_settings(), "require_email_verification", True)
    register(anonymous_client)
    blocked = anonymous_client.get("/api/v1/datasets")
    assert blocked.status_code == 403 and blocked.json()["code"] == "email_not_verified"
    assert anonymous_client.get(f"{AUTH}/me").status_code == 200  # the UI still needs to know who they are

    anonymous_client.post(f"{AUTH}/verify-email", json={"token": token_in(outbox[0])})
    assert anonymous_client.get("/api/v1/datasets").status_code == 200


def test_verification_is_not_required_by_default(anonymous_client, outbox):
    register(anonymous_client)
    assert anonymous_client.get("/api/v1/datasets").status_code == 200


def test_resend_verification_only_mails_unverified_accounts(anonymous_client, outbox):
    register(anonymous_client)
    assert anonymous_client.post(f"{AUTH}/resend-verification").status_code == 202
    assert len(outbox) == 2
    anonymous_client.post(f"{AUTH}/verify-email", json={"token": token_in(outbox[1])})
    anonymous_client.post(f"{AUTH}/resend-verification")
    assert len(outbox) == 2


def test_resend_verification_needs_a_session(anonymous_client, outbox):
    assert anonymous_client.post(f"{AUTH}/resend-verification").status_code == 401


# --- password reset ---------------------------------------------------------------------------


def test_forgot_password_answers_identically_for_unknown_emails(anonymous_client, outbox):
    register(anonymous_client)
    outbox.clear()
    known = anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "new@example.com"})
    unknown = anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.text == unknown.text
    assert [m.to for m in outbox] == ["new@example.com"]


def test_reset_password_sets_a_new_password_and_ends_old_sessions(anonymous_client, outbox):
    from tests.conftest import new_client

    register(anonymous_client)
    anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "new@example.com"})
    token = token_in(outbox[-1])

    resp = anonymous_client.post(f"{AUTH}/reset-password", json={"token": token, "password": NEW_PASSWORD})
    assert resp.status_code == 204
    assert anonymous_client.get(f"{AUTH}/me").status_code == 401  # the old cookie is dead

    fresh = new_client()
    assert login(fresh, password=PASSWORD).status_code == 401
    assert login(fresh, password=NEW_PASSWORD).status_code == 200


def test_reset_link_works_only_once(anonymous_client, outbox):
    register(anonymous_client)
    anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "new@example.com"})
    token = token_in(outbox[-1])
    first = anonymous_client.post(f"{AUTH}/reset-password", json={"token": token, "password": NEW_PASSWORD})
    again = anonymous_client.post(
        f"{AUTH}/reset-password", json={"token": token, "password": "yet another passphrase"}
    )
    assert first.status_code == 204 and again.status_code == 400


def test_reset_rejects_short_passwords_and_verification_tokens(anonymous_client, outbox):
    register(anonymous_client)
    anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "new@example.com"})
    reset = token_in(outbox[-1])
    short = anonymous_client.post(f"{AUTH}/reset-password", json={"token": reset, "password": "short"})
    assert short.status_code == 400 and short.json()["code"] == "validation_error"
    verify = token_in(outbox[0])
    assert (
        anonymous_client.post(
            f"{AUTH}/reset-password", json={"token": verify, "password": NEW_PASSWORD}
        ).status_code
        == 400
    )


def test_reset_also_verifies_the_email(anonymous_client, outbox):
    register(anonymous_client)
    anonymous_client.post(f"{AUTH}/forgot-password", json={"email": "new@example.com"})
    anonymous_client.post(
        f"{AUTH}/reset-password", json={"token": token_in(outbox[-1]), "password": NEW_PASSWORD}
    )
    login(anonymous_client, password=NEW_PASSWORD)
    assert anonymous_client.get(f"{AUTH}/me").json()["email_verified_at"] is not None


# --- change password --------------------------------------------------------------------------


def test_change_password_requires_the_current_one_and_keeps_this_device_signed_in(
    anonymous_client, outbox
):
    from tests.conftest import new_client

    register(anonymous_client)
    wrong = anonymous_client.post(
        f"{AUTH}/change-password", json={"current_password": "wrong password!", "new_password": NEW_PASSWORD}
    )
    assert wrong.status_code == 400 and wrong.json()["code"] == "invalid_credentials"

    ok = anonymous_client.post(
        f"{AUTH}/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert ok.status_code == 200
    assert anonymous_client.get(f"{AUTH}/me").status_code == 200
    assert login(new_client(), password=PASSWORD).status_code == 401
    assert login(new_client(), password=NEW_PASSWORD).status_code == 200


def test_change_password_rejects_reuse_and_anonymous_callers(anonymous_client, outbox):
    body = {"current_password": PASSWORD, "new_password": PASSWORD}
    assert anonymous_client.post(f"{AUTH}/change-password", json=body).status_code == 401
    register(anonymous_client)
    assert anonymous_client.post(f"{AUTH}/change-password", json=body).status_code == 400


def test_production_refuses_required_verification_without_smtp():
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        assert_safe_for_environment(
            Settings(
                environment="production", secret_key="x" * 40, cookie_secure=True,
                require_email_verification=True, smtp_host="",
            )
        )
