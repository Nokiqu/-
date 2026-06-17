from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import DeliveryDatabase


@pytest.fixture
def runtime_dir():
    root = PROJECT_ROOT / ".test_runtime"
    root.mkdir(exist_ok=True)
    case_dir = root / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir()
    return case_dir


@pytest.fixture
def database(runtime_dir):
    db = DeliveryDatabase(runtime_dir / "delivery.db")
    db.init_db()
    return db
