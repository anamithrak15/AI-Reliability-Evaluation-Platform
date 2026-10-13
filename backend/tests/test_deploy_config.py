import pytest
from starlette.requests import Request

from app.core.client_ip import client_ip
from app.core.config import Settings, get_settings


def fake_request(forwarded: str | None, peer: str = "10.0.0.9") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234), "method": "GET", "path": "/"})


@pytest.fixture
def hops(monkeypatch):
    def _set(n):
        monkeypatch.setattr(get_settings(), "trusted_proxy_hops", n)

    return _set


def test_without_trusted_proxies_the_forwarded_header_is_ignored(hops):
    hops(0)
    assert client_ip(fake_request("6.6.6.6")) == "10.0.0.9"


def test_one_proxy_uses_the_address_it_appended(hops):
    hops(1)
    assert client_ip(fake_request("203.0.113.5")) == "203.0.113.5"


def test_two_proxies_such_as_vercel_then_render(hops):
    hops(2)
    assert client_ip(fake_request("203.0.113.5, 76.76.21.21")) == "203.0.113.5"


def test_spoofed_entries_added_by_the_caller_are_ignored(hops):
    hops(2)
    assert client_ip(fake_request("1.1.1.1, 203.0.113.5, 76.76.21.21")) == "203.0.113.5"
    hops(1)
    assert client_ip(fake_request("1.1.1.1, 203.0.113.5")) == "203.0.113.5"


@pytest.mark.parametrize("header", [None, "", "  , "])
def test_missing_header_falls_back_to_the_connection_peer(hops, header):
    hops(2)
    assert client_ip(fake_request(header)) == "10.0.0.9"


def test_too_few_entries_falls_back_instead_of_trusting_a_partial_chain(hops):
    hops(3)
    assert client_ip(fake_request("203.0.113.5")) == "10.0.0.9"


def test_missing_peer_is_reported_as_unknown(hops):
    hops(0)
    request = Request({"type": "http", "headers": [], "client": None, "method": "GET", "path": "/"})
    assert client_ip(request) == "unknown"


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ],
)
def test_host_provided_database_urls_get_the_psycopg_driver(given, expected):
    assert Settings(database_url=given).database_url == expected
