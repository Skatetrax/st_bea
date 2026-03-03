# Skatetrax Backend API
Turns models from Skatetrax Core into routes in flask.

## Auth & Registration

Auth business logic (user CRUD, roles, invite tokens, password reset) lives in `skatetrax_core` at `skatetrax/auth/service.py`. The Flask layer has two thin adapters: `app/user_datastore.py` (a `UserDatastore` subclass required by Flask-Security-Too) and `app/blueprints/auth_routes.py` (route handlers that parse requests and call the core service). All auth endpoints live under `/api/v4/auth`.

### Endpoints

#### `GET /api/v4/auth/register/validate-token?token=<token>`
Frontend preflight to check if an invite token is valid before showing the registration form.

**Response:** `{"valid": true}` or `403` with a message (`"Registration is currently invite-only."` / `"This invite has expired or has already been used."`).

#### `POST /api/v4/auth/register`
Create a new user account. Registration is invite-only.

**Payload:**
```json
{
  "aLogin": "username",
  "aEmail": "user@example.com",
  "aPasswordHash": "plaintext_password",
  "phone_number": "555-0100",
  "invite_token": "your-invite-token",
  "roles": ["adult", "coach"]
}
```

- `roles` is optional (defaults to `["adult"]`). Multi-select from: `adult`, `coach`, `guardian`. `minor` is rejected -- minors cannot self-register.
- `invite_token` is required. Tokens are validated and consumed on successful registration.

#### `POST /api/v4/auth/login`
Authenticate and start a session.

**Payload:**
```json
{
  "aLogin": "username",
  "aPasswordHash": "plaintext_password"
}
```

**Response:** `{"message": "Login successful"}` with a session cookie. Also accepts `aEmail` instead of `aLogin`.

#### `GET /api/v4/auth/session`
Check the current session state.

**Response (authenticated):**
```json
{
  "logged_in": true,
  "user_id": 1,
  "uSkaterUUID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "onboarding_complete": false
}
```

`onboarding_complete` is `true` when a `uSkaterConfig` row exists for this user's `uSkaterUUID`.

**Response (unauthenticated):** `401` with `{"logged_in": false}`.

#### `POST /api/v4/auth/onboard`
Complete the onboarding walkthrough (requires login). Creates the `uSkaterConfig` profile row.

**Payload:**
```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "city": "Denver",
  "state": "CO",
  "country": "US",
  "zip": "80202",
  "timezone": "America/Denver",
  "coach_id": null,
  "rink_id": null,
  "skate_config": null
}
```

- `first_name` and `last_name` are required. All other fields are optional.
- Returns `409` if onboarding is already complete for this user.

#### `POST /api/v4/auth/change-password`
Change the current user's password (requires login).

**Payload:**
```json
{
  "current_password": "old_password",
  "new_password": "new_password"
}
```

- Verifies the current password before updating.
- Returns `401` if current password is incorrect.

#### `POST /api/v4/auth/reset-request`
Request a password reset email (public, no login required).

**Payload:**
```json
{
  "email": "user@example.com"
}
```

- Always returns `200` with `"If that email is registered, a reset link has been sent."` to prevent email enumeration.
- Returns `503` if the email service is not configured (missing `MAIL_SERVER` env var).
- Reset tokens expire after 1 hour.

#### `POST /api/v4/auth/reset-confirm`
Reset a password using a token from the reset email (public, no login required).

**Payload:**
```json
{
  "token": "reset-token-from-email",
  "new_password": "new_password"
}
```

- Returns `400` if the token is invalid, expired, or already used.

#### `POST /api/v4/auth/logout`
End the current session.

**Response:** `{"message": "Logged out"}`.

### Email configuration

Password reset emails require Flask-Mail. Set these env vars to enable:

- `MAIL_SERVER` -- SMTP host (e.g. `smtp.example.com`). **If not set, Flask-Mail is not initialized and the app runs without email.**
- `MAIL_PORT` -- defaults to `587`
- `MAIL_USE_TLS` -- defaults to `true`
- `MAIL_USERNAME` / `MAIL_PASSWORD` -- SMTP credentials
- `MAIL_DEFAULT_SENDER` -- defaults to `noreply@skatetrax.com`
- `RESET_URL_BASE` -- frontend reset page URL (e.g. `https://skatetrax.app/reset`). The token is appended as `?token=...`.

### Deployment / Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| **Database** ||||
| `PGDB_HOST` | **Yes** | *(none)* | PostgreSQL host (e.g. `127.0.0.1` or a cloud hostname). |
| `PGDB_NAME` | **Yes** | *(none)* | Database name (e.g. `skatetrax`). |
| `PGDB_USER` | **Yes** | *(none)* | Database user. |
| `PGDB_PASSWORD` | **Yes** | *(none)* | Database password. |
| `PGDB_SSLMODE` | No | *(unset)* | PostgreSQL `sslmode` parameter (e.g. `require`). Omit for local dev. |
| **Flask / Session** ||||
| `FLASK_SECRET_KEY` | **Yes** (production) | ephemeral random key | Signs session cookies. Must be a stable secret shared across replicas. In dev, an ephemeral key is auto-generated with a warning. |
| `FLASK_ENV` | No | *(unset)* | Set to `production` to enforce strict checks (e.g. missing `FLASK_SECRET_KEY` raises a `RuntimeError`). |
| `CORS_ORIGIN` | No | localhost regex | Comma-separated list of allowed origins (e.g. `https://app.skatetrax.com,http://localhost:3000`). When unset, defaults to a regex matching `localhost`, `127.0.0.1`, and `192.168.*` on port 3000. |
| `SESSION_COOKIE_SECURE` | No | `false` | Set to `true` when running behind TLS so cookies are only sent over HTTPS. |
| `SESSION_COOKIE_DOMAIN` | No | *(unset -- uses request host)* | Explicit cookie domain. Leave unset unless you need cross-subdomain cookies. |
| `SECURITY_PASSWORD_SALT` | No | `skatetrax-salt` | Salt used by Flask-Security-Too for token generation. |
| **Email** ||||
| `MAIL_SERVER` | No | *(unset)* | SMTP host. If not set, Flask-Mail is not initialized and password-reset emails are unavailable. |
| `MAIL_PORT` | No | `587` | SMTP port. |
| `MAIL_USE_TLS` | No | `false` | Enable STARTTLS (port 587). Mutually exclusive with `MAIL_USE_SSL`. |
| `MAIL_USE_SSL` | No | `false` | Enable implicit SSL (port 465). Mutually exclusive with `MAIL_USE_TLS`. |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | No | *(unset)* | SMTP credentials. |
| `MAIL_DEFAULT_SENDER` | No | `noreply@skatetrax.com` | From address for outgoing email. |
| `RESET_URL_BASE` | No | *(unset)* | Frontend password-reset page URL. Token is appended as `?token=...`. |

### Two-phase user setup

1. **Registration** creates the `uAuthTable` auth record and assigns roles. The user can authenticate but has no skater profile yet.
2. **Onboarding** creates the `uSkaterConfig` profile (name, location, coach, rink, equipment). Until onboarding completes, `GET /session` returns `"onboarding_complete": false`.

### Protected routes

All data routes (dashboard, ice_time, equipment, maintenance, etc.) use `@login_required`. User identity comes from `current_user` (Flask-Login); `uSkaterUUID` drives data aggregation.

---

### Contributing & Release Process
Anything in the `main` branch should work as expected with as little effort as possible.  The `dev` branch is where new features, defined by milestones, can be added prior to a release.  Currently, there is no schedule for releases, but once all items in a milestone are completed, they should be merged into `main`, with the exception of bug/break fixes.

If you're interested in suggesting changes, please fork the repo, check out the `dev` branch, and create a feature branch from that.  Once a PR is opened against our `dev` branch, it can be reviewed and pulled into `main`. There are no naming requirements for PR's or branches, though the project default relies on a year/week_numberPushIdentifier, `2024_47A` for example indicates the 2024 year, week 47, first push/merge (A) for that week. If a second feature is worked on that week, the branch for that would be `2024_47B`.

Input/comments/feedback for any open PR is always welcome.