from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.security.pinned_http import create_pinned_async_transport
from app.security.url_validator import validate_provider_url


@dataclass(frozen=True)
class OidcConfig:
    enabled: bool
    issuer_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    allowed_domains: list[str]
    auto_provision: bool

    @property
    def configured(self) -> bool:
        return bool(
            self.enabled
            and self.issuer_url
            and self.client_id
            and self.client_secret
            and self.redirect_uri
        )


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    return []


def load_oidc_config(config: dict[str, Any]) -> OidcConfig:
    return OidcConfig(
        enabled=_coerce_bool(config.get("oidc_enabled"), False),
        issuer_url=str(config.get("oidc_issuer_url", "")).rstrip("/"),
        client_id=str(config.get("oidc_client_id", "")),
        client_secret=str(config.get("oidc_client_secret", "")),
        redirect_uri=str(config.get("oidc_redirect_uri", "")),
        allowed_domains=_coerce_list(config.get("oidc_allowed_domains")),
        auto_provision=_coerce_bool(config.get("oidc_auto_provision"), False),
    )


async def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    clean_url, resolved_ip = validate_provider_url(url)
    async with httpx.AsyncClient(
        timeout=10.0,
        transport=create_pinned_async_transport(clean_url, resolved_ip),
    ) as client:
        response = await client.get(clean_url, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OIDC endpoint did not return a JSON object")
    return payload


async def _post_form(
    url: str,
    *,
    data: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    clean_url, resolved_ip = validate_provider_url(url)
    async with httpx.AsyncClient(
        timeout=15.0,
        transport=create_pinned_async_transport(clean_url, resolved_ip),
    ) as client:
        response = await client.post(clean_url, data=data, headers=headers)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("OIDC endpoint did not return a JSON object")
    return payload


async def _discover(config: OidcConfig) -> dict[str, Any]:
    data = await _get_json(f"{config.issuer_url}/.well-known/openid-configuration")
    issuer = str(data.get("issuer", "")).rstrip("/")
    if issuer and issuer != config.issuer_url:
        raise ValueError("OIDC issuer mismatch")
    return data


async def build_authorization_url(config: OidcConfig, state: str) -> str:
    if not config.configured:
        raise ValueError("OIDC is not configured")
    discovery = await _discover(config)
    authorization_endpoint = str(discovery.get("authorization_endpoint", ""))
    if not authorization_endpoint:
        raise ValueError("OIDC authorization endpoint missing")
    query = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
    )
    return f"{authorization_endpoint}?{query}"


async def exchange_code_for_userinfo(config: OidcConfig, code: str) -> dict[str, Any]:
    if not config.configured:
        raise ValueError("OIDC is not configured")
    discovery = await _discover(config)
    token_endpoint = str(discovery.get("token_endpoint", ""))
    userinfo_endpoint = str(discovery.get("userinfo_endpoint", ""))
    if not token_endpoint or not userinfo_endpoint:
        raise ValueError("OIDC token or userinfo endpoint missing")
    token_data = await _post_form(
        token_endpoint,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    access_token = str(token_data.get("access_token", ""))
    if not access_token:
        raise ValueError("OIDC access token missing")
    return await _get_json(
        userinfo_endpoint,
        headers={"Authorization": f"Bearer {access_token}"},
    )
