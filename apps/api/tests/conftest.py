from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings
from app.supabase import get_supabase

CONFIG_VARIABLES = ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "CORS_ORIGINS", "ALLOW_LIVE")


@pytest.fixture(autouse=True)
def clean_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Run every test with no config env and no `.env` file, and fresh caches."""
    for name in CONFIG_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    # Settings reads `.env` from the working directory; point it at an empty one.
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    get_supabase.cache_clear()
    yield
    get_settings.cache_clear()
    get_supabase.cache_clear()
