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
