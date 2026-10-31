from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


class MissingConfigError(RuntimeError):
    """A setting needed to build the Supabase client is not set."""

    def __init__(self, variable: str) -> None:
        super().__init__(
            f"{variable} is not set. Set it in the environment or in apps/api/.env "
            "(see apps/api/.env.example)."
        )
        self.variable = variable


@lru_cache
def get_supabase() -> Client:
    """Return the shared Supabase client, creating it on first use.

    Uses the server-only secret key, so it bypasses row level security. Call it
    from request handlers or dependencies, never at import time. A failure is
    not cached, so setting the variable and calling again works.
    """
    settings = get_settings()
    if not settings.SUPABASE_URL:
        raise MissingConfigError("SUPABASE_URL")
    secret_key = settings.SUPABASE_SECRET_KEY.get_secret_value()
    if not secret_key:
        raise MissingConfigError("SUPABASE_SECRET_KEY")
    return create_client(settings.SUPABASE_URL, secret_key)
