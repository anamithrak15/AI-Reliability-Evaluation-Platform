import io
import json
import logging
import urllib.error

import pytest

from app.core.config import get_settings
from app.services import mailer
from app.services.mailer import Mail

MAIL = Mail(to="user@example.com", subject="Hello", body="Body with a link")


@pytest.fixture
def brevo(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from", "AI Reliability <sender@example.com>")


def test_brevo_request_carries_sender_recipient_and_key(brevo, monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        seen["url"], seen["timeout"] = request.full_url, timeout
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data)
        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    mailer.send(MAIL)

    assert seen["url"] == "https://api.brevo.com/v3/smtp/email" and seen["timeout"] == 15
    assert seen["headers"]["api-key"] == "test-key"
    assert seen["body"] == {
        "sender": {"email": "sender@example.com", "name": "AI Reliability"},
        "to": [{"email": "user@example.com"}],
        "subject": "Hello",
        "textContent": "Body with a link",
    }


def test_brevo_http_error_is_logged_with_its_reason_and_not_raised(brevo, monkeypatch, caplog):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"message":"sender not verified"}')
        )

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with caplog.at_level(logging.ERROR):
        mailer.send(MAIL)
    assert "HTTP 400" in caplog.text and "sender not verified" in caplog.text
    assert "test-key" not in caplog.text


def test_network_failure_is_logged_by_type_and_not_raised(brevo, monkeypatch, caplog):
    def time_out(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", time_out)
    with caplog.at_level(logging.ERROR):
        mailer.send(MAIL)
    assert "TimeoutError" in caplog.text


def test_production_counts_either_method_as_deliverable(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "brevo_api_key", "")
    assert mailer.can_deliver() is False
    monkeypatch.setattr(settings, "brevo_api_key", "k")
    assert mailer.can_deliver() is True
