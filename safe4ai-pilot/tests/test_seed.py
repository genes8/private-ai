from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_seed_flushes_admin_before_creating_documents() -> None:
    seed_py = (ROOT / "scripts" / "seed.py").read_text()

    flush_idx = seed_py.index("db.flush()")
    document_loop_idx = seed_py.index("for filename, content in _SAMPLE_DOCS")

    assert flush_idx < document_loop_idx


def test_seed_writes_sample_files_and_runs_ingestion() -> None:
    seed_py = (ROOT / "scripts" / "seed.py").read_text()

    assert "storage_path.write_text(content, encoding=\"utf-8\")" in seed_py
    assert "from app.services.ingestion_service import run_ingestion" in seed_py
    assert "await run_ingestion(" in seed_py
    assert "asyncio.run(seed())" in seed_py
