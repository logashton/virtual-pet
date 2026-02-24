# API reference

Base URL: `/api/`

Auth for protected routes: send header `Authorization: Token <your_token>`.

---

## Auth (`/api/auth/`)

### Register

`POST /api/auth/register/`

Body (JSON):

| Field         | Type   | Required |
|---------------|--------|----------|
| email         | string | yes      |
| username      | string | yes      |
| password      | string | yes (min 8) |
| display_name  | string | no       |

Returns `201` with `{ "token": "...", "user": { "id", "email", "username", "display_name" } }`.  
Errors: `400` if email/username taken or validation fails.

### Login

`POST /api/auth/login/`

Body (JSON): `email`, `password`.

Returns `200` with `{ "token": "...", "user": { "id", "email", "username", "display_name" } }`.  
`401` invalid credentials, `403` if account disabled.

### Current user

`GET /api/auth/me/`

Requires auth. Returns `200` with `{ "id", "email", "username", "display_name" }`.

---

## Pets (`/api/pets/`)

### List pets

`GET /api/pets/?scope=mine`  
Your pets. Auth required.

`GET /api/pets/?scope=public`  
Public, non-archived pets. No auth.

`GET /api/pets/` with no `scope`: if you’re logged in, same as `scope=mine`; if not, returns `400` and asks you to use `scope=mine` or `scope=public`.

Response: array of pet objects. Each has `id`, `owner` (id, username, display_name), `name`, `visibility`, `is_archived`, `created_at`, `updated_at`, `last_interaction_at`.

### Create pet

`POST /api/pets/`

Auth required. Owner is the current user.

Body (JSON):

| Field       | Type    | Required |
|-------------|---------|----------|
| name        | string  | yes      |
| visibility  | string  | no (default `"private"`) — `"private"` \| `"public"` \| `"unlisted"` |
| is_archived | boolean | no (default false) |

Returns `201` with the full pet object.

### Get one pet

`GET /api/pets/<id>/`

- **private** pets: only the owner can read; everyone else gets `404`.
- **public** / **unlisted**: anyone can read.

Returns `200` with the pet object or `404`.

### Update pet

`PATCH /api/pets/<id>/`

Owner only. Body can include any of: `name`, `visibility`, `is_archived` (partial update).  
Returns `200` with updated pet. `403` if not owner, `404` if pet doesn’t exist.

### Delete pet

`DELETE /api/pets/<id>/`

Owner only. Returns `204` on success. `403` if not owner, `404` if pet doesn’t exist.

---

## Moderation reports (`/api/moderation-reports/`)

All endpoints require authentication.

### List reports

`GET /api/moderation-reports/`

- **Non-staff:** returns only reports created by the current user.
- **Staff:** returns all reports.

Query params (optional):

| Param | Description |
|-------|-------------|
| `pet` | Filter by pet id (integer). |

Returns `200` with an array of report objects: `id`, `reporter_user`, `pet`, `asset`, `reason`, `details`, `status`, `created_at`, `resolved_at`.

### Create report

`POST /api/moderation-reports/`

Body (JSON): at least one of `pet_id` or `asset_id` is required.

| Field    | Type   | Required |
|----------|--------|----------|
| reason   | string | yes      |
| details  | string | no       |
| pet_id   | int    | no (one of pet_id / asset_id required) |
| asset_id | int    | no       |

`reporter_user` is set from the current user. Returns `201` with the created report. `400` if validation fails.

### Get one report

`GET /api/moderation-reports/<id>/`

Reporter or staff only. Returns `200` with the report object or `404`.

### Update report (staff only)

`PATCH /api/moderation-reports/<id>/`

Body can include: `status`, `resolved_at`. Returns `200` with updated report. `403` if not staff.

### Delete report (staff only)

`DELETE /api/moderation-reports/<id>/`

Returns `204` on success. `403` if not staff.

---

## Admin (`/api/admin/`)

All endpoints require authentication and **superuser** (`is_superuser`).

### List users

`GET /api/admin/users/`

Returns `200` with an array of user objects: `id`, `email`, `username`, `display_name`, `is_active`, `is_staff`, `is_superuser`, `created_at`.

### Get one user

`GET /api/admin/users/<id>/`

Returns `200` with the user object or `404`.

### Update user

`PATCH /api/admin/users/<id>/`

Body can include: `email`, `username`, `display_name`, `is_active`, `is_staff`, `is_superuser`. Returns `200` with updated user. Email and username must be unique (excluding the user being updated).

### Delete user

`DELETE /api/admin/users/<id>/`

Returns `204` on success. Cannot delete your own account (`400`).

---

## Pets – admin list

`GET /api/pets/?scope=all`

Superuser only. Returns all pets (including private and archived). Same response shape as list pets.
