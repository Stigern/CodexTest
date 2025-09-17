from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app


@pytest.fixture(autouse=True)
def fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "printer_service.db"
    monkeypatch.setattr(app, "DB_FILE", str(db_path))
    app.initialize_database()
    yield


def _create_sample_printer(name="Printer 1", printer_id="printer-1", **overrides):
    params = {
        "printer_id": printer_id,
        "name": name,
        "manufacturer": overrides.get("manufacturer", "Maker"),
        "model": overrides.get("model", "Model X"),
        "hours": overrides.get("hours", 5),
        "nozzle_type": overrides.get("nozzle_type", "0.4 mm"),
        "ams": overrides.get("ams", False),
    }
    app.db_insert_printer(**params)
    return app.db_fetch_printers()[0]


def test_ensure_unique_printer_id_increments_suffix():
    _create_sample_printer(printer_id="machine")
    assert app.ensure_unique_printer_id("machine") == "machine-2"

    app.db_insert_printer(
        "machine-2",
        "Printer Copy",
        "Maker",
        "Model",
        0,
        "0.4 mm",
        False,
    )
    assert app.ensure_unique_printer_id("machine") == "machine-3"


def test_ensure_unique_printer_id_defaults_to_generic_name():
    assert app.ensure_unique_printer_id("   ") == "printer"


def test_log_crud_and_cascade_delete():
    printer_db_id, *_ = _create_sample_printer()

    # Insert and update a log entry
    app.db_insert_log(printer_db_id, "Initial log entry")
    log_id, created_at, note = app.db_fetch_logs_for(printer_db_id)[0]
    assert note == "Initial log entry"
    assert created_at

    app.db_update_log(log_id, "Updated log entry")
    updated_log = app.db_fetch_logs_for(printer_db_id)[0]
    assert updated_log[2] == "Updated log entry"

    # Deleting the printer should cascade to the log table
    app.db_delete_printer(printer_db_id)

    with app.get_connection() as conn:
        remaining_logs = conn.execute("SELECT COUNT(*) FROM service_logs").fetchone()[0]
        remaining_printers = conn.execute("SELECT COUNT(*) FROM printers").fetchone()[0]

    assert remaining_logs == 0
    assert remaining_printers == 0
