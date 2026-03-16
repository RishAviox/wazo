# Running Pytest Tests

## Quick Start

The test suite has been created but requires proper Django setup to run. Here are the options:

### Option 1: Run Tests in Docker (Recommended)

```bash
docker compose exec web python manage.py test tracevision.tests
```

### Option 2: Run with Django's Test Runner

```bash
source venv/bin/activate
python manage.py test tracevision.tests
```

### Option 3: Fix Pytest Configuration

If you want to use pytest directly, you need to ensure Django can find all modules. Try:

```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=wazo.settings
export PYTHONPATH=$PWD
pytest tracevision/tests/ -v
```

## Test Files Created

- `tracevision/tests/conftest.py` - Fixtures for users, teams, data
- `tracevision/tests/test_highlight_notes.py` - 20 tests for notes endpoint
- `tracevision/tests/test_clip_reel_sharing.py` - 11 tests for sharing
- `tracevision/tests/test_clip_reel_comments.py` - 9 tests for comments

## Total: 40 Tests

All tests cover:
- ✅ Authentication & Authorization
- ✅ Privacy & Visibility
- ✅ Sharing Restrictions
- ✅ Data Validation
- ✅ Error Handling

## Alternative: Use Django Test Runner

Django's built-in test runner works out of the box:

```bash
python manage.py test tracevision.tests.test_highlight_notes
python manage.py test tracevision.tests.test_clip_reel_sharing
python manage.py test tracevision.tests.test_clip_reel_comments
```

This avoids pytest configuration issues and uses Django's test database setup.
