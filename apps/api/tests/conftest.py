from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["MODEL_GATEWAY_MODE"] = "mock"


@pytest.fixture(autouse=True)
def reset_database():
    from app.database import init_db

    init_db(drop_existing=True)
    yield

@pytest.fixture(autouse=True)
def use_fallback_model_gateway(monkeypatch):
    from app.core.model_gateway import ModelGateway, ModelResult

    def fake_generate(self, *, messages, purpose, fallback):
        return ModelResult(
            content=fallback.strip(),
            model_provider="mock",
            model_name=f"mock-{purpose}",
            input_token_count=1,
            output_token_count=max(1, len(fallback) // 2),
        )

    monkeypatch.setattr(ModelGateway, "generate", fake_generate)
