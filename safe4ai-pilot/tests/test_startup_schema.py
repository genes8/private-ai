from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_startup_initializes_pgvector_extension_before_tables() -> None:
    main_py = (ROOT / "app" / "main.py").read_text()

    extension_idx = main_py.index("CREATE EXTENSION IF NOT EXISTS vector")
    create_all_idx = main_py.index("Base.metadata.create_all")

    assert extension_idx < create_all_idx


def test_startup_creates_schema_before_recovering_jobs() -> None:
    main_py = (ROOT / "app" / "main.py").read_text()

    create_all_idx = main_py.index("Base.metadata.create_all")
    recover_idx = main_py.index("recover_stuck_jobs(db)")

    assert create_all_idx < recover_idx
