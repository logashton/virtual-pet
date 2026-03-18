# Testing

## Running tests

with virtualenv activated and dependencies installed:

# Run all tests (core + chat)
python manage.py test core chat

## Configuration

- **Database:** When running tests, the project uses an in-memory SQLite database (`:memory:`), so no real database is modified.
- **Media:** `MEDIA_ROOT` is set to a temporary directory during tests so upload tests do not touch project media files.
- Test mode is enabled when `test` is in `sys.argv` (e.g. `manage.py test`), when `DJANGO_TESTING=1`, or when the process is started via pytest.

## What’s tested

- **Core**
  - **Models:** User (create_user / create_superuser), Pet, PetAsset (image and 3D), PetStats, PetPersonality.
  - **Auth API:** Register, login, `/api/auth/me/` (401 when anonymous, 200 when authenticated).
  - **Pets API:** List (mine/public), create, detail (get/patch/delete), image upload, 3D model upload, personality PATCH, stats GET.
  - **Web helpers:** `_pet_card_data()` (has_3d, image_url, description).
  - **Remove-background API:** Auth required, missing image → 400, success → PNG (rembg mocked).
  - **Image-to-3D API:** Auth required, missing image → 400, success → GLB (pipeline mocked).
- **Chat**
  - **Chat API:** GET history (empty when unauthenticated, session + messages when authenticated; private pet → 404 for non-owner). POST message (success with mocked LLM, 400 when message body missing). Pet not found → 404.

Remove-background, image-to-3d, and chat tests **mock** external or heavy behaviour (rembg, mesh/GLB generation, LLM HTTP calls) so the suite can run without those services or heavy dependencies.
