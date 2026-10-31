import pytest

from app.supabase import MissingConfigError, get_supabase

FAKE_SECRET = "sb_secret_fake_value_for_tests"


def test_missing_url_names_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_SECRET_KEY", FAKE_SECRET)

    with pytest.raises(MissingConfigError, match="SUPABASE_URL") as excinfo:
        get_supabase()

    assert FAKE_SECRET not in str(excinfo.value)


def test_missing_secret_key_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")

    with pytest.raises(MissingConfigError, match="SUPABASE_SECRET_KEY") as excinfo:
        get_supabase()

    assert "127.0.0.1" not in str(excinfo.value)


def test_nothing_set_fails_on_first_variable() -> None:
    with pytest.raises(MissingConfigError, match="SUPABASE_URL"):
        get_supabase()


def test_client_is_created_lazily_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A JWT-shaped fake key: the client parses it locally and makes no request.
    fake_key = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.fake"
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", fake_key)

    first = get_supabase()

    assert get_supabase() is first
