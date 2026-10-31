"""Route test harness: the fixture CSV, no key, no network."""

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.runs import RunService
from app.config import Settings
from app.main import create_app
from app.negotiation import dot

FIXTURE = (
    Path(__file__).parent.parent / "negotiation" / "fixtures" / "flights_sample.csv"
)


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


@pytest.fixture
def flights_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A private copy, because the SQLite cache is written beside the CSV."""
    data = tmp_path / "data"
    data.mkdir()
    csv = data / "flights.csv"
    shutil.copy(FIXTURE, csv)
    monkeypatch.setenv(dot.ENV_CSV, str(csv))
    yield csv
    dot.clear_connections()


@pytest.fixture
def recordings(tmp_path: Path) -> Path:
    path = tmp_path / "recordings"
    path.mkdir()
    return path


@pytest.fixture
def results(tmp_path: Path) -> Path:
    path = tmp_path / "eval_results"
    path.mkdir()
    return path


type ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(flights_csv: Path, recordings: Path, results: Path) -> ClientFactory:
    def build(*, allow_live: bool = False, live_client: Any = None) -> TestClient:
        settings = Settings(ALLOW_LIVE=allow_live)
        service = RunService(
            settings,
            recordings_dir=recordings,
            results_dir=results,
            live_client=live_client,
        )
        return TestClient(create_app(settings, service))

    return build


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()
