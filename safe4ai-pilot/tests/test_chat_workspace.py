"""Tests for chat active-workspace resolution (`_resolve_active_workspace`)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.chat_routes import _resolve_active_workspace


def _request(workspace_header: str | None) -> SimpleNamespace:
    headers = {"X-Workspace-Id": workspace_header} if workspace_header else {}
    return SimpleNamespace(headers=headers)


def test_header_workspace_returned_for_member() -> None:
    user = MagicMock()
    with patch("app.services.workspace_service.assert_member", return_value=None):
        result = _resolve_active_workspace(_request("ws-a"), user, MagicMock())
    assert result == "ws-a"


def test_header_workspace_non_member_is_404() -> None:
    from app.services import workspace_service

    user = MagicMock()
    with patch(
        "app.services.workspace_service.assert_member",
        side_effect=workspace_service.WorkspaceAccessDenied("ws-a"),
    ):
        with pytest.raises(HTTPException) as exc:
            _resolve_active_workspace(_request("ws-a"), user, MagicMock())
    assert exc.value.status_code == 404


def test_no_header_single_workspace_used() -> None:
    user = MagicMock()
    with patch(
        "app.services.workspace_service.list_workspace_ids_for_user",
        return_value=["only-ws"],
    ):
        result = _resolve_active_workspace(_request(None), user, MagicMock())
    assert result == "only-ws"


def test_no_header_multiple_workspaces_requires_selection() -> None:
    user = MagicMock()
    with patch(
        "app.services.workspace_service.list_workspace_ids_for_user",
        return_value=["ws-a", "ws-b"],
    ):
        with pytest.raises(HTTPException) as exc:
            _resolve_active_workspace(_request(None), user, MagicMock())
    assert exc.value.status_code == 400
