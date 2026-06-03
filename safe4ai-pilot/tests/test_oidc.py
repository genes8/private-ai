from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.auth.oidc import OidcConfig, build_authorization_url, exchange_code_for_userinfo


def _config() -> OidcConfig:
    return OidcConfig(
        enabled=True,
        issuer_url="https://idp.example.com",
        client_id="safe4ai",
        client_secret="secret-value",  # noqa: S106
        redirect_uri="http://localhost:8000/auth/sso/callback",
        allowed_domains=["example.com"],
        auto_provision=False,
    )


@pytest.mark.anyio
async def test_oidc_authorization_discovery_uses_ssrf_validated_pinned_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[str] = []

    def _validate(url: str) -> tuple[str, str]:
        validated.append(url)
        return url.rstrip("/"), "93.184.216.34"

    def _transport(url: str, resolved_ip: str) -> httpx.MockTransport:
        assert url == "https://idp.example.com/.well-known/openid-configuration"
        assert resolved_ip == "93.184.216.34"
        return httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "issuer": "https://idp.example.com",
                    "authorization_endpoint": "https://idp.example.com/authorize",
                },
            )
        )

    monkeypatch.setattr("app.auth.oidc.validate_provider_url", _validate)
    monkeypatch.setattr("app.auth.oidc.create_pinned_async_transport", _transport)

    authorize_url = await build_authorization_url(_config(), "state-123")

    assert validated == ["https://idp.example.com/.well-known/openid-configuration"]
    assert authorize_url.startswith("https://idp.example.com/authorize?")


@pytest.mark.anyio
async def test_oidc_token_and_userinfo_endpoints_are_ssrf_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[str] = []

    def _validate(url: str) -> tuple[str, str]:
        validated.append(url)
        return url.rstrip("/"), "93.184.216.34"

    def _transport(url: str, resolved_ip: str) -> httpx.MockTransport:
        assert resolved_ip == "93.184.216.34"

        def _handle(request: httpx.Request) -> httpx.Response:
            responses: dict[str, dict[str, Any]] = {
                "/.well-known/openid-configuration": {
                    "issuer": "https://idp.example.com",
                    "token_endpoint": "https://idp.example.com/token",
                    "userinfo_endpoint": "https://idp.example.com/userinfo",
                },
                "/token": {"access_token": "access-token"},
                "/userinfo": {"email": "alice@example.com"},
            }
            return httpx.Response(200, json=responses[request.url.path])

        return httpx.MockTransport(_handle)

    monkeypatch.setattr("app.auth.oidc.validate_provider_url", _validate)
    monkeypatch.setattr("app.auth.oidc.create_pinned_async_transport", _transport)

    userinfo = await exchange_code_for_userinfo(_config(), "code-123")

    assert userinfo["email"] == "alice@example.com"
    assert validated == [
        "https://idp.example.com/.well-known/openid-configuration",
        "https://idp.example.com/token",
        "https://idp.example.com/userinfo",
    ]
