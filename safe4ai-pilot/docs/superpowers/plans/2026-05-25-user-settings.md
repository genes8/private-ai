# User Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a user-facing `/settings` page where authenticated users can view account, usage, and knowledge base status, and change their own password.

**Architecture:** Add account-scoped backend routes under `/account/*` that require `get_current_user` but not admin role. Keep these routes separate from admin `/settings`, then add a frontend account API module and a compact `/settings` page linked from the chat header.

**Tech Stack:** FastAPI, SQLAlchemy ORM, bcrypt auth helpers, React, React Router, TanStack Query, Tailwind CSS, lucide-react.

---

## File Structure

- Create `safe4ai-pilot/app/api/account_routes.py`
  - Owns current-user account settings serialization and password change.
  - Depends on `get_current_user`, `get_db`, `hash_password`, and `verify_password`.

- Modify `safe4ai-pilot/app/main.py`
  - Imports and includes the new `account_router`.

- Create `safe4ai-pilot/tests/test_account.py`
  - Covers account settings aggregation, user scoping, password validation, password update, and token invalidation.

- Create `safe4ai-pilot/frontend/src/api/account.ts`
  - Defines `AccountSettings`, `ChangePasswordRequest`, `getAccountSettings`, and `changePassword`.

- Create `safe4ai-pilot/frontend/src/pages/SettingsPage.tsx`
  - User-facing settings page with account, security, usage, and knowledge base sections.
  - Owns password form state and validation.

- Modify `safe4ai-pilot/frontend/src/App.tsx`
  - Adds authenticated `/settings` route.

- Modify `safe4ai-pilot/frontend/src/pages/ChatPage.tsx`
  - Adds a settings icon link near the avatar for all authenticated users.

---

### Task 1: Backend Account API Tests

**Files:**
- Create: `safe4ai-pilot/tests/test_account.py`

- [ ] **Step 1: Write failing backend tests**

Create `safe4ai-pilot/tests/test_account.py` with:

```python
from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.middleware import encode_token, hash_password, verify_password
from app.db import get_db
from app.db.models import User, UserRole
from app.main import app


def _make_user(
    *,
    user_id: str = "user-1",
    email: str = "alice@example.com",
    role: UserRole = UserRole.pilot_user,
    password_hash: str | None = None,
    created_at: datetime | None = None,
) -> User:
    user = User()
    user.id = user_id
    user.email = email
    user.role = role
    user.is_active = True
    user.password_hash = password_hash or hash_password("CurrentPass123!")
    user.created_at = created_at or datetime(2026, 5, 25, tzinfo=UTC)
    user.token_valid_after = None
    return user


def _override_get_db(db: MagicMock) -> Callable[[], Generator[MagicMock, None, None]]:
    def _override() -> Generator[MagicMock, None, None]:
        yield db

    return _override


def _authenticated_client(db: MagicMock, user: User) -> TestClient:
    app.dependency_overrides[get_db] = _override_get_db(db)
    client = TestClient(app)
    role = getattr(user.role, "value", user.role)
    client.cookies.set("access_token", encode_token(str(user.id), str(role)))
    client.cookies.set("csrf_token", "csrf-test-token")
    client.headers["X-CSRF-Token"] = "csrf-test-token"
    return client


def _cleanup_overrides() -> None:
    app.dependency_overrides.clear()


def _scalar_query(value: object) -> MagicMock:
    query = MagicMock()
    query.filter.return_value = query
    query.scalar.return_value = value
    return query


@contextmanager
def _account_config_patch() -> Iterator[None]:
    try:
        with patch("app.api.account_routes.load_app_config", return_value={}):
            yield
    except ModuleNotFoundError:
        yield


def test_account_settings_succeeds_for_pilot_user() -> None:
    user = _make_user()
    db = MagicMock()
    db.get.return_value = user
    db.query.side_effect = [
        _scalar_query(3),
        _scalar_query(7),
        _scalar_query(2),
        _scalar_query(1),
        _scalar_query(None),
        _scalar_query(5),
        _scalar_query(120),
        _scalar_query(0),
        _scalar_query(1),
    ]

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.get("/account/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["email"] == "alice@example.com"
    assert body["profile"]["role"] == "pilot_user"
    assert body["profile"]["isActive"] is True
    assert body["security"]["sessionHours"] == 24
    assert body["security"]["passwordChangeAllowed"] is True
    assert body["usage"]["questions7d"] == 3
    assert body["usage"]["questions30d"] == 7
    assert body["usage"]["feedbackPositive"] == 2
    assert body["usage"]["feedbackNegative"] == 1
    assert body["knowledgeBase"]["docCount"] == 5
    assert body["knowledgeBase"]["chunkCount"] == 120


def test_account_settings_filters_usage_by_current_user() -> None:
    user = _make_user(user_id="user-scope")
    db = MagicMock()
    db.get.return_value = user
    scoped_queries = [_scalar_query(0) for _ in range(9)]
    db.query.side_effect = scoped_queries

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.get("/account/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    audit_7d_filter_args = scoped_queries[0].filter.call_args.args
    audit_30d_filter_args = scoped_queries[1].filter.call_args.args
    positive_feedback_filter_args = scoped_queries[2].filter.call_args.args
    negative_feedback_filter_args = scoped_queries[3].filter.call_args.args
    assert any("audit_logs.user_id" in str(arg) for arg in audit_7d_filter_args)
    assert any("audit_logs.user_id" in str(arg) for arg in audit_30d_filter_args)
    assert any("query_feedback.user_id" in str(arg) for arg in positive_feedback_filter_args)
    assert any("query_feedback.user_id" in str(arg) for arg in negative_feedback_filter_args)


def test_change_password_rejects_wrong_current_password() -> None:
    user = _make_user(password_hash=hash_password("CurrentPass123!"))
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "WrongPass123!", "newPassword": "NewStrongPass123!"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 401
    assert "Current password is incorrect" in response.json()["detail"]
    db.commit.assert_not_called()


def test_change_password_rejects_weak_new_password() -> None:
    user = _make_user(password_hash=hash_password("CurrentPass123!"))
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "CurrentPass123!", "newPassword": "short"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 422
    assert "Password must be at least 12 characters" in response.json()["detail"]
    db.commit.assert_not_called()


def test_change_password_updates_hash_and_invalidates_tokens() -> None:
    old_hash = hash_password("CurrentPass123!")
    user = _make_user(password_hash=old_hash)
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        with _account_config_patch():
            response = client.post(
                "/account/change-password",
                json={"currentPassword": "CurrentPass123!", "newPassword": "NewStrongPass123!"},
            )
    finally:
        _cleanup_overrides()

    assert response.status_code == 200
    assert response.json() == {"message": "Password changed. Please sign in again with your new password."}
    assert user.password_hash != old_hash
    assert verify_password("NewStrongPass123!", user.password_hash)
    assert user.token_valid_after is not None
    assert user.token_valid_after <= datetime.now(UTC)
    db.commit.assert_called_once()


def test_admin_settings_remains_admin_only_for_pilot_user() -> None:
    user = _make_user(role=UserRole.pilot_user)
    db = MagicMock()
    db.get.return_value = user

    client = _authenticated_client(db, user)
    try:
        response = client.get("/settings")
    finally:
        _cleanup_overrides()

    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd safe4ai-pilot
.venv/bin/pytest tests/test_account.py -q
```

Expected: FAIL with 404 responses for `/account/settings` and `/account/change-password`.

- [ ] **Step 3: Commit failing tests**

```bash
git add safe4ai-pilot/tests/test_account.py
git commit -m "test: cover user account settings API"
```

---

### Task 2: Backend Account API Implementation

**Files:**
- Create: `safe4ai-pilot/app/api/account_routes.py`
- Modify: `safe4ai-pilot/app/main.py`
- Test: `safe4ai-pilot/tests/test_account.py`

- [ ] **Step 1: Create account routes**

Create `safe4ai-pilot/app/api/account_routes.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.middleware import get_current_user, hash_password, verify_password
from app.db import get_db
from app.db.models import (
    AuditLog,
    Document,
    DocumentChunk,
    FeedbackRating,
    IngestionStatus,
    QueryFeedback,
    User,
)
from app.services.app_config_store import load_app_config

router = APIRouter(prefix="/account", tags=["account"])


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


def _validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(not char.isalnum() for char in password)
    if not (has_upper and has_lower and has_digit and has_special):
        raise HTTPException(
            status_code=422,
            detail="Password must include uppercase, lowercase, digit, and special character",
        )


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return str(value)


@router.get("/settings")
def get_account_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    config = load_app_config(db)
    session_hours = int(config.get("session_hours", 24) or 24)
    sso_only = bool(config.get("sso_only", False))

    questions_7d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.user_id == current_user.id, AuditLog.timestamp >= seven_days_ago)
        .scalar()
        or 0
    )
    questions_30d = (
        db.query(func.count(AuditLog.id))
        .filter(AuditLog.user_id == current_user.id, AuditLog.timestamp >= thirty_days_ago)
        .scalar()
        or 0
    )
    feedback_positive = (
        db.query(func.count(QueryFeedback.id))
        .filter(
            QueryFeedback.user_id == current_user.id,
            QueryFeedback.rating == FeedbackRating.positive,
        )
        .scalar()
        or 0
    )
    feedback_negative = (
        db.query(func.count(QueryFeedback.id))
        .filter(
            QueryFeedback.user_id == current_user.id,
            QueryFeedback.rating == FeedbackRating.negative,
        )
        .scalar()
        or 0
    )
    last_activity_at = (
        db.query(func.max(AuditLog.timestamp))
        .filter(AuditLog.user_id == current_user.id)
        .scalar()
    )

    doc_count = db.query(func.count(Document.id)).scalar() or 0
    chunk_count = db.query(func.count(DocumentChunk.id)).scalar() or 0
    failed_count = (
        db.query(func.count(Document.id))
        .filter(Document.ingestion_status == IngestionStatus.failed)
        .scalar()
        or 0
    )
    in_progress_count = (
        db.query(func.count(Document.id))
        .filter(Document.ingestion_status.in_([IngestionStatus.embedding, IngestionStatus.queued]))
        .scalar()
        or 0
    )

    return {
        "profile": {
            "id": current_user.id,
            "email": current_user.email,
            "role": getattr(current_user.role, "value", current_user.role),
            "isActive": current_user.is_active,
            "createdAt": _iso_or_none(current_user.created_at),
        },
        "security": {
            "sessionHours": session_hours,
            "ssoOnly": sso_only,
            "passwordChangeAllowed": not sso_only,
        },
        "usage": {
            "questions7d": int(questions_7d),
            "questions30d": int(questions_30d),
            "lastActivityAt": _iso_or_none(last_activity_at),
            "feedbackPositive": int(feedback_positive),
            "feedbackNegative": int(feedback_negative),
        },
        "knowledgeBase": {
            "docCount": int(doc_count),
            "chunkCount": int(chunk_count),
            "failedCount": int(failed_count),
            "inProgressCount": int(in_progress_count),
        },
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    config = load_app_config(db)
    if bool(config.get("sso_only", False)):
        raise HTTPException(status_code=403, detail="Password changes are disabled while SSO is required")

    if not verify_password(body.currentPassword, str(current_user.password_hash)):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    _validate_password_strength(body.newPassword)
    current_user.password_hash = hash_password(body.newPassword)
    current_user.token_valid_after = datetime.now(UTC)
    db.commit()
    return {"message": "Password changed. Please sign in again with your new password."}
```

- [ ] **Step 2: Include account router in app**

Modify `safe4ai-pilot/app/main.py` imports:

```python
from app.api.account_routes import router as account_router
from app.api.admin_routes import router as admin_router
from app.api.chat_routes import router as chat_router
from app.api.observability_routes import router as observability_router
from app.api.settings_routes import router as settings_router
```

Modify router includes:

```python
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(observability_router)
app.include_router(admin_router)
app.include_router(settings_router)
app.include_router(account_router)
```

- [ ] **Step 3: Run backend tests**

Run:

```bash
cd safe4ai-pilot
.venv/bin/pytest tests/test_account.py tests/test_auth.py tests/test_admin.py::TestMe tests/test_admin.py::TestCorpusStats -q
```

Expected: PASS for the selected account/auth/admin tests.

- [ ] **Step 4: Commit backend API**

```bash
git add safe4ai-pilot/app/api/account_routes.py safe4ai-pilot/app/main.py safe4ai-pilot/tests/test_account.py
git commit -m "feat: add user account settings API"
```

---

### Task 3: Frontend Account API And Routing

**Files:**
- Create: `safe4ai-pilot/frontend/src/api/account.ts`
- Modify: `safe4ai-pilot/frontend/src/App.tsx`
- Modify: `safe4ai-pilot/frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Add account API client**

Create `safe4ai-pilot/frontend/src/api/account.ts`:

```ts
import { apiFetch } from "./client";

export interface AccountSettings {
  profile: {
    id: string;
    email: string;
    role: "admin" | "pilot_user";
    isActive: boolean;
    createdAt: string | null;
  };
  security: {
    sessionHours: number;
    ssoOnly: boolean;
    passwordChangeAllowed: boolean;
  };
  usage: {
    questions7d: number;
    questions30d: number;
    lastActivityAt: string | null;
    feedbackPositive: number;
    feedbackNegative: number;
  };
  knowledgeBase: {
    docCount: number;
    chunkCount: number;
    failedCount: number;
    inProgressCount: number;
  };
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

export const getAccountSettings = () =>
  apiFetch<AccountSettings>("/account/settings");

export const changePassword = (body: ChangePasswordRequest) =>
  apiFetch<{ message: string }>("/account/change-password", {
    method: "POST",
    body: JSON.stringify(body),
  });
```

- [ ] **Step 2: Add placeholder settings page for routing**

Create `safe4ai-pilot/frontend/src/pages/SettingsPage.tsx`:

```tsx
export default function SettingsPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-paper">
      <span className="text-[13px] text-text-mute">Loading settings...</span>
    </div>
  );
}
```

- [ ] **Step 3: Add authenticated `/settings` route**

Modify `safe4ai-pilot/frontend/src/App.tsx` imports:

```tsx
import SettingsPage from "./pages/SettingsPage";
```

Add this route before the wildcard route:

```tsx
<Route
  path="/settings"
  element={
    <RequireAuth>
      <ErrorBoundary><SettingsPage /></ErrorBoundary>
    </RequireAuth>
  }
/>
```

- [ ] **Step 4: Link chat header to user settings**

Modify `safe4ai-pilot/frontend/src/pages/ChatPage.tsx` so the existing `Settings` icon import is used for the user settings link. In the header button group, add this link before the admin-only button:

```tsx
<Link to="/settings">
  <Button variant="ghost" size="sm" iconLeft={<Settings size={13} />}>Settings</Button>
</Link>
```

Keep the existing admin-only `Admin` button. If the two buttons use the same `Settings` icon, the label distinguishes them.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd safe4ai-pilot/frontend
npm run build
```

Expected: PASS with Vite production build output.

- [ ] **Step 6: Commit frontend route scaffolding**

```bash
git add safe4ai-pilot/frontend/src/api/account.ts safe4ai-pilot/frontend/src/App.tsx safe4ai-pilot/frontend/src/pages/ChatPage.tsx safe4ai-pilot/frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add user settings route"
```

---

### Task 4: Frontend User Settings Page

**Files:**
- Modify: `safe4ai-pilot/frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Replace placeholder with full page implementation**

Replace `safe4ai-pilot/frontend/src/pages/SettingsPage.tsx` with:

```tsx
import { AlertCircle, ArrowLeft, CheckCircle2, KeyRound, LogOut, Shield, UserRound } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Avatar from "../components/Avatar";
import Button from "../components/Button";
import Logo from "../components/Logo";
import { ApiError } from "../api/client";
import { changePassword, getAccountSettings } from "../api/account";
import { useAuth } from "../hooks/useAuth";

function formatDate(value: string | null) {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function passwordIssue(password: string, confirmPassword: string): string | null {
  if (password.length < 12) return "Use at least 12 characters.";
  if (!/[A-Z]/.test(password)) return "Add at least one uppercase letter.";
  if (!/[a-z]/.test(password)) return "Add at least one lowercase letter.";
  if (!/[0-9]/.test(password)) return "Add at least one digit.";
  if (!/[^A-Za-z0-9]/.test(password)) return "Add at least one special character.";
  if (password !== confirmPassword) return "New passwords do not match.";
  return null;
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3">{label}</div>
      <div className="mt-1 text-[20px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4 last:border-b-0">
      <div className="text-[13px] font-medium text-ink">{label}</div>
      <div className="max-w-[60%] truncate text-right font-mono text-[12px] text-text-2">{value}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["account-settings"],
    queryFn: getAccountSettings,
    staleTime: 30_000,
    retry: 1,
  });

  const validationError = useMemo(
    () => passwordIssue(newPassword, confirmPassword),
    [newPassword, confirmPassword],
  );
  const canSubmit =
    currentPassword.length > 0 &&
    newPassword.length > 0 &&
    confirmPassword.length > 0 &&
    validationError === null;

  const passwordMutation = useMutation({
    mutationFn: changePassword,
    onSuccess: (result) => {
      setSuccessMessage(result.message);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      queryClient.clear();
      window.setTimeout(() => {
        navigate("/login", { replace: true });
      }, 1400);
    },
  });

  function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || passwordMutation.isPending) return;
    passwordMutation.mutate({ currentPassword, newPassword });
  }

  const knowledgeStatus = data?.knowledgeBase.failedCount
    ? "Needs admin attention"
    : data?.knowledgeBase.inProgressCount
    ? "Indexing"
    : "Healthy";

  return (
    <div className="flex h-screen flex-col bg-paper">
      <header className="flex items-center justify-between border-b border-line bg-surface px-5 py-3">
        <div className="flex items-center gap-3">
          <Logo size={22} />
          <span className="text-[13.5px] font-medium tracking-tight text-ink">private·ai</span>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/chat">
            <Button variant="ghost" size="sm" iconLeft={<ArrowLeft size={13} />}>Chat</Button>
          </Link>
          <Avatar name={me?.email ?? "U"} size={26} />
          <button
            type="button"
            onClick={signOut}
            aria-label="Sign out"
            className="text-text-mute transition-colors hover:text-text-2"
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-6 py-8">
          <div className="mb-8">
            <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-[0.06em] text-text-3">account</div>
            <h1 className="font-serif text-[30px] italic tracking-tight text-ink">Settings</h1>
            <p className="mt-1.5 max-w-[62ch] text-[13.5px] leading-relaxed text-text-2">
              Manage your account password and review your recent private·ai usage.
            </p>
          </div>

          {isLoading && (
            <div className="rounded-lg border border-line bg-surface px-5 py-8 text-center text-[13px] text-text-mute">
              Loading settings...
            </div>
          )}

          {isError && (
            <div className="rounded-lg border border-danger/20 bg-danger-soft px-5 py-4 text-[13px] text-danger">
              <div className="mb-3 flex items-center gap-2">
                <AlertCircle size={16} />
                <span>{error instanceof Error ? error.message : "Failed to load settings."}</span>
              </div>
              <Button variant="danger" size="sm" onClick={() => void refetch()}>Retry</Button>
            </div>
          )}

          {data && (
            <div className="space-y-8">
              <section>
                <div className="mb-4 flex items-center gap-2">
                  <UserRound size={16} className="text-text-3" />
                  <h2 className="font-serif text-[20px] italic text-ink">Account</h2>
                </div>
                <div className="overflow-hidden rounded-lg border border-line bg-surface">
                  <Field label="Email" value={data.profile.email} />
                  <Field label="Role" value={data.profile.role} />
                  <Field label="Status" value={data.profile.isActive ? "Active" : "Inactive"} />
                  <Field label="Created" value={formatDate(data.profile.createdAt)} />
                </div>
              </section>

              <section>
                <div className="mb-4 flex items-center gap-2">
                  <Shield size={16} className="text-text-3" />
                  <h2 className="font-serif text-[20px] italic text-ink">Security</h2>
                </div>
                <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
                  <div className="overflow-hidden rounded-lg border border-line bg-surface">
                    <Field label="Session lifetime" value={`${data.security.sessionHours} hours`} />
                    <Field label="Password login" value={data.security.ssoOnly ? "Disabled by SSO" : "Enabled"} />
                    <Field label="Password changes" value={data.security.passwordChangeAllowed ? "Allowed" : "Disabled"} />
                  </div>

                  <form onSubmit={submitPassword} className="rounded-lg border border-line bg-surface p-5">
                    <div className="mb-4 flex items-center gap-2">
                      <KeyRound size={15} className="text-text-3" />
                      <div className="text-[13.5px] font-medium text-ink">Change password</div>
                    </div>
                    <div className="space-y-3">
                      <input
                        type="password"
                        value={currentPassword}
                        onChange={(event) => setCurrentPassword(event.target.value)}
                        placeholder="Current password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                      <input
                        type="password"
                        value={newPassword}
                        onChange={(event) => setNewPassword(event.target.value)}
                        placeholder="New password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        placeholder="Confirm new password"
                        disabled={!data.security.passwordChangeAllowed}
                        className="h-9 w-full rounded border border-line bg-surface px-3 font-mono text-[12.5px] outline-none focus:border-accent disabled:opacity-50"
                      />
                    </div>

                    {newPassword && confirmPassword && validationError && (
                      <p className="mt-3 text-[12px] text-danger">{validationError}</p>
                    )}
                    {passwordMutation.error && (
                      <p className="mt-3 text-[12px] text-danger">
                        {passwordMutation.error instanceof ApiError
                          ? passwordMutation.error.message
                          : "Password change failed."}
                      </p>
                    )}
                    {successMessage && (
                      <p className="mt-3 flex items-center gap-2 text-[12px] text-success">
                        <CheckCircle2 size={14} />
                        {successMessage}
                      </p>
                    )}

                    <div className="mt-4">
                      <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        loading={passwordMutation.isPending}
                        disabled={!canSubmit || !data.security.passwordChangeAllowed}
                      >
                        Change password
                      </Button>
                    </div>
                  </form>
                </div>
              </section>

              <section>
                <h2 className="mb-4 font-serif text-[20px] italic text-ink">Usage</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <StatTile label="Questions 7d" value={data.usage.questions7d} />
                  <StatTile label="Questions 30d" value={data.usage.questions30d} />
                  <StatTile label="Thumbs up" value={data.usage.feedbackPositive} />
                  <StatTile label="Thumbs down" value={data.usage.feedbackNegative} />
                  <StatTile label="Last activity" value={formatDate(data.usage.lastActivityAt)} />
                </div>
              </section>

              <section>
                <h2 className="mb-4 font-serif text-[20px] italic text-ink">Knowledge base</h2>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <StatTile label="Status" value={knowledgeStatus} />
                  <StatTile label="Documents" value={data.knowledgeBase.docCount} />
                  <StatTile label="Chunks" value={data.knowledgeBase.chunkCount} />
                  <StatTile label="Failed" value={data.knowledgeBase.failedCount} />
                  <StatTile label="Indexing" value={data.knowledgeBase.inProgressCount} />
                </div>
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd safe4ai-pilot/frontend
npm run build
```

Expected: PASS with Vite production build output.

- [ ] **Step 3: Commit full settings page**

```bash
git add safe4ai-pilot/frontend/src/pages/SettingsPage.tsx
git commit -m "feat: build user settings page"
```

---

### Task 5: Final Verification

**Files:**
- Verify: `safe4ai-pilot/app/api/account_routes.py`
- Verify: `safe4ai-pilot/frontend/src/pages/SettingsPage.tsx`
- Verify: `safe4ai-pilot/frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: Run backend account/auth/admin regression**

Run:

```bash
cd safe4ai-pilot
.venv/bin/pytest tests/test_account.py tests/test_auth.py tests/test_admin.py::TestMe tests/test_admin.py::TestCorpusStats -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd safe4ai-pilot/frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Verify route access manually with local app**

Start backend and frontend using the repo's normal local commands:

```bash
cd safe4ai-pilot
uvicorn app.main:app --reload
```

```bash
cd safe4ai-pilot/frontend
npm run dev
```

Manual checks:

- Log in as a `pilot_user`.
- Open `/settings`.
- Confirm account, security, usage, and knowledge base sections render.
- Confirm `/admin/settings` redirects or blocks the `pilot_user`.
- Submit mismatched new passwords and confirm the submit button remains disabled.
- Submit a weak new password and confirm inline validation.
- Submit the correct current password with a strong new password.
- Confirm the message `Password changed. Please sign in again with your new password.` appears.
- Confirm the app navigates to `/login`.
- Confirm logging in with the old password fails and the new password succeeds.

- [ ] **Step 4: Final status check**

Run:

```bash
git status --short
```

Expected: only intentional changes are present. Existing unrelated `.qoder/` and `promo-screenshots/` changes may remain if they predate this implementation.

- [ ] **Step 5: Commit verification-only fixes if needed**

If verification exposes a small defect in the files touched by this plan, fix it and commit with:

```bash
git add safe4ai-pilot/app/api/account_routes.py safe4ai-pilot/app/main.py safe4ai-pilot/tests/test_account.py safe4ai-pilot/frontend/src/api/account.ts safe4ai-pilot/frontend/src/App.tsx safe4ai-pilot/frontend/src/pages/ChatPage.tsx safe4ai-pilot/frontend/src/pages/SettingsPage.tsx
git commit -m "fix: polish user settings flow"
```

---

## Self-Review

Spec coverage:

- User-facing `/settings` route is covered in Task 3.
- Account, security, usage, and knowledge base sections are covered in Task 4.
- Password change with current password verification and strength checks is covered in Tasks 1, 2, and 4.
- Sign-in-again success message is covered in Tasks 1 and 4.
- Existing token invalidation through `token_valid_after` is covered in Tasks 1 and 2.
- Current-user usage scoping is covered in Tasks 1 and 2.
- Admin `/settings` remaining admin-only is covered in Tasks 1 and 5.
- Build and regression verification are covered in Tasks 3, 4, and 5.

Placeholder scan:

- No placeholder sections are intentionally left for implementers.
- Every code-changing step includes concrete code or exact insertion content.
- Every verification step includes exact commands and expected outcomes.

Type consistency:

- Backend response keys use camelCase to match frontend `AccountSettings`.
- `ChangePasswordRequest` uses `currentPassword` and `newPassword` in backend and frontend.
- Frontend route path `/settings` matches the design spec.
