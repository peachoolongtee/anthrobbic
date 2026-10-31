"""The safety core must not be able to reach a model or the network."""

import json
import os
import pkgutil
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]

# Top-level module names. Anything that imports one of these can call a model
# or make an HTTP request.
FORBIDDEN = [
    "anthropic",
    "openai",
    "google.generativeai",
    "google.genai",
    "cohere",
    "mistralai",
    "groq",
    "litellm",
    "langchain",
    "httpx",
    "requests",
    "aiohttp",
    "urllib3",
    "httpcore",
    "http.client",
    "urllib.request",
    "supabase",
    "fastapi",
]


def test_importing_the_package_loads_no_llm_sdk_or_http_client() -> None:
    script = f"""
import importlib, json, pkgutil, sys
import app.negotiation as pkg
names = ["app.negotiation"]
for info in pkgutil.walk_packages(pkg.__path__, "app.negotiation."):
    if ".agents" in info.name:
        continue  # later slices put the model calls there, behind their own gate
    importlib.import_module(info.name)
    names.append(info.name)
forbidden = {FORBIDDEN!r}
loaded = sorted(
    m for m in sys.modules
    if any(m == f or m.startswith(f + ".") for f in forbidden)
)
print(json.dumps({{"loaded": loaded, "modules": names}}))
"""
    env = {**os.environ, "PYTHONPATH": str(API_ROOT)}
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(done.stdout)
    assert report["loaded"] == []
    # The walk really covered the core modules.
    for module in (
        "app.negotiation.contracts",
        "app.negotiation.rule_values",
        "app.negotiation.options",
        "app.negotiation.utility",
        "app.negotiation.fallback",
        "app.negotiation.rules.atc",
        "app.negotiation.rules.pilot",
        "app.negotiation.rules.ground",
    ):
        assert module in report["modules"]


def test_the_guard_would_notice_a_forbidden_import() -> None:
    script = "import httpx, sys; print('httpx' in sys.modules)"
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=API_ROOT,
        env={**os.environ, "PYTHONPATH": str(API_ROOT)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == "True"


def test_no_core_source_names_a_forbidden_module() -> None:
    core = API_ROOT / "app" / "negotiation"
    for info in pkgutil.walk_packages([str(core)]):
        assert not info.name.startswith(("anthropic", "openai"))
    for path in core.rglob("*.py"):
        if "agents" in path.parts:
            continue
        text = path.read_text()
        for module in FORBIDDEN:
            assert f"import {module}" not in text, (path, module)
            assert f"from {module}" not in text, (path, module)
