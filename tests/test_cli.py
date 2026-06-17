from __future__ import annotations

from main_cli import main


def test_cli_init_report_and_export(runtime_dir, capsys):
    db_path = runtime_dir / "cli.db"
    export_path = runtime_dir / "backup.json"

    assert main(["--db", str(db_path), "init-db", "--seed"]) == 0
    assert main(["--db", str(db_path), "report", "--period", "month"]) == 0
    report_output = capsys.readouterr().out
    assert "Количество заказов по статусам" in report_output

    assert main(["--db", str(db_path), "export", "--file", str(export_path)]) == 0
    assert export_path.exists()


def test_cli_import(runtime_dir):
    source_db = runtime_dir / "source.db"
    target_db = runtime_dir / "target.db"
    export_path = runtime_dir / "backup.xml"

    assert main(["--db", str(source_db), "init-db", "--seed"]) == 0
    assert main(["--db", str(source_db), "export", "--file", str(export_path)]) == 0

    assert main(["--db", str(target_db), "init-db"]) == 0
    assert main(["--db", str(target_db), "import", "--file", str(export_path)]) == 0
