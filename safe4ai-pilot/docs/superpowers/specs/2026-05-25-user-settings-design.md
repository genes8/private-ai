# User Settings Design

Date: 2026-05-25
Status: Backend implemented; frontend pending

## Progress

Last updated: 2026-05-25

### Done

- Design spec written and committed in `bb32635 docs: add user settings design spec`.
- Backend contract tests added and reviewed in `e893e03 test: add account settings contract tests`.
- Account-scoped backend API implemented and reviewed in `240327e Add account settings routes`.
- `GET /account/settings` now exists for authenticated users and returns profile, security, usage, and knowledge base aggregates.
- Usage aggregation is scoped to `current_user.id`.
- Knowledge base counts are read-only corpus-level aggregates.
- `POST /account/change-password` now verifies the current password, enforces shared password strength policy, updates the password hash, invalidates existing tokens, and returns the sign-in-again message.
- Password strength policy is shared between admin user creation and account password change.
- JWT `iat` precision was adjusted so old tokens are rejected after password change while a fresh immediate login token is accepted.
- `/settings` backend admin configuration remains admin-only.

Backend verification completed:

- `tests/test_account.py` passes.
- `tests/test_auth.py` account/auth regression coverage passes.
- Relevant admin user, `/me`, and corpus-status tests pass.
- Review evidence included a focused run of `tests/test_account.py tests/test_auth.py tests/test_admin.py`.

### In Progress / Not Counted As Done

- A partial untracked frontend file exists at `safe4ai-pilot/frontend/src/api/account.ts` from an interrupted Task 3 attempt. It has not been reviewed, committed, or counted as complete.
- The implementation plan exists at `safe4ai-pilot/docs/superpowers/plans/2026-05-25-user-settings.md` but is still untracked at the time of this update.

### Remaining

- Add the frontend account API module and commit it after review.
- Add authenticated `/settings` route in `frontend/src/App.tsx`.
- Add a user-visible settings link in `frontend/src/pages/ChatPage.tsx` for ordinary users while keeping the admin console link for admins.
- Build the full user settings page with Account, Security, Usage, and Knowledge Base sections.
- Implement frontend password form validation and success flow:
  - current password
  - new password
  - confirm password
  - strength validation
  - success message: `Password changed. Please sign in again with your new password.`
  - clear auth/query state and navigate to `/login`
- Run frontend build.
- Run final backend regression checks.
- Manually verify `/settings`, password change, re-login, and admin-only `/admin/settings` behavior.

## Goal

Add a settings page for ordinary authenticated users. The page should help a user understand their own account, change their password, and see a short summary of their own usage and the knowledge base status.

This page is separate from the existing admin settings page. Admin settings remain responsible for system-wide configuration such as providers, models, retrieval, security policy, cost ceilings, and document administration.

## Non-Goals

- Ordinary users cannot change global application settings.
- Ordinary users cannot change model, provider, retrieval, audit retention, or cost settings.
- Ordinary users cannot upload, delete, or reindex documents from this page.
- Ordinary users cannot see other users' usage, feedback, audit events, prompts, traces, or admin-only operational details.
- The page will not expose API keys, provider names, internal model names, or detailed audit logs.

## User Experience

Add a user-facing settings route at `/settings`, reachable from the chat header near the avatar. Admin users can also access this account settings page, while the existing Admin button continues to lead to the admin console.

The settings page uses the same quiet operational visual language as the current chat and admin UI, but it does not use the admin sidebar. It should have a compact app header with navigation back to Chat, avatar/account context, and sign out.

The page contains four sections:

1. Account
   - Email
   - Role
   - Account active status
   - Created date from the existing user model

2. Security
   - Change password form
   - Session lifetime as read-only information
   - SSO/password state as read-only information
   - Sign out action remains available

3. Usage
   - Questions in the last 7 days
   - Questions in the last 30 days
   - Last activity timestamp
   - Positive feedback count
   - Negative feedback count

4. Knowledge Base
   - Document count
   - Chunk count
   - Failed indexing count
   - In-progress indexing count
   - A short, read-only status label such as healthy, indexing, or needs admin attention

## Password Change Flow

The password form contains:

- Current password
- New password
- Confirm new password

Client-side validation should check:

- New password and confirmation match
- Minimum length of 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character

Server-side validation must enforce the same password strength rules. The server must verify the current password before updating the stored password hash.

After a successful password change, the app shows this message:

> Password changed. Please sign in again with your new password.

The frontend then clears local auth/query state and sends the user to `/login`. The backend should update `token_valid_after` so existing tokens are invalidated.

## Backend API

Add account-scoped endpoints for authenticated users. Do not reuse or broaden the existing admin-only `/settings` endpoint.

### `GET /account/settings`

Requires any authenticated user.

Returns only current-user and read-only aggregate data:

```json
{
  "profile": {
    "id": "string",
    "email": "user@example.com",
    "role": "pilot_user",
    "isActive": true,
    "createdAt": "2026-05-25T00:00:00Z"
  },
  "security": {
    "sessionHours": 24,
    "ssoOnly": false,
    "passwordChangeAllowed": true
  },
  "usage": {
    "questions7d": 0,
    "questions30d": 0,
    "lastActivityAt": null,
    "feedbackPositive": 0,
    "feedbackNegative": 0
  },
  "knowledgeBase": {
    "docCount": 0,
    "chunkCount": 0,
    "failedCount": 0,
    "inProgressCount": 0
  }
}
```

Usage fields must be filtered by `current_user.id`. Knowledge base fields can be corpus-level aggregate counts because they are already shown in the chat experience and do not expose document contents.

### `POST /account/change-password`

Requires any authenticated user.

Request:

```json
{
  "currentPassword": "string",
  "newPassword": "string"
}
```

Behavior:

- Reject if the current password is incorrect.
- Reject if the new password fails strength validation.
- Store the new password hash using the existing password hashing helper.
- Set `token_valid_after` to the current time.
- Return a success response that allows the frontend to show the sign-in-again message.

## Data Sources

- Profile comes from the current `User` record.
- Session lifetime and SSO-only state come from `app_config` with existing defaults.
- Usage comes from current-user rows in `AuditLog` and `QueryFeedback`.
- Knowledge base counts come from `Document` and `DocumentChunk`, using the same status semantics as the admin corpus status endpoint.

## Error Handling

- If the settings payload fails to load, show a page-level retry state.
- If only usage or knowledge base aggregates fail, the page can show an unavailable state for that section without hiding the account/security section.
- Incorrect current password is an inline form error.
- Weak new password is an inline form error.
- Expired session uses the existing unauthorized handling and redirects to login.
- Successful password change always shows the sign-in-again message before or during redirect to `/login`.

## Access Control

`GET /account/settings` and `POST /account/change-password` require `get_current_user`, not `require_role("admin")`.

All usage aggregation must include a current-user filter. The account API must not return prompt text, response text, trace IDs, other users' records, provider settings, API key state, or admin-only operational settings.

The existing `/admin/settings` route remains admin-only and keeps its current behavior.

## Testing

Backend tests:

- `GET /account/settings` succeeds for `pilot_user`.
- `GET /account/settings` returns only current-user usage aggregates.
- `POST /account/change-password` rejects an incorrect current password.
- `POST /account/change-password` rejects a weak new password.
- `POST /account/change-password` updates the password hash on success.
- `POST /account/change-password` updates `token_valid_after`.
- `/admin/settings` remains admin-only.

Frontend tests or focused verification:

- `/settings` requires authentication.
- Chat header exposes the settings link for ordinary users.
- Password form validates match and strength before submit.
- Successful password change displays `Password changed. Please sign in again with your new password.`
- Successful password change clears auth state and navigates to login.

Build and regression checks:

- Run backend pytest for account/auth/admin-related tests.
- Run the frontend build.
- Verify that existing admin settings behavior is unchanged.
