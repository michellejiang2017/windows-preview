import tempfile
import pytest
from fastapi.testclient import TestClient
from rag.app.ingestion import ingest, split, MAX_BYTES
from rag.app.service import RagService
from rag.app import main


@pytest.fixture(scope="module")
def service():
    # Chroma's Windows index handles stay open until its system is stopped.
    with tempfile.TemporaryDirectory() as path:
        svc = RagService(path)
        try:
            yield svc
        finally:
            svc.db._system.stop()
            svc.db.clear_system_cache()


def test_ingestion_metadata():
    chunks = ingest(b"name,value\nalpha,42\nbeta,99\n", "table.csv")
    assert chunks[1].metadata["row"] == 2 and "beta" in chunks[1].text
    assert chunks[1].metadata["location"] == "data row 2 (CSV line 3)"
    from rag.app.models import ROOT

    pdf = ingest((ROOT / "samples/preview-demo.pdf").read_bytes(), "sample.pdf")
    assert {c.metadata["page"] for c in pdf} == {1, 4}


@pytest.mark.parametrize(
    "data,name",
    [
        (b"", "a.txt"),
        (b"bad", "a.pdf"),
        (b"\xff", "a.txt"),
        (b"a,a\n1,2", "a.csv"),
        (b"a\n1,2", "a.csv"),
        (b"x", "a.exe"),
    ],
)
def test_invalid_inputs(data, name):
    with pytest.raises(ValueError):
        ingest(data, name)


def test_chunk_bounds_and_limits():
    chunks = list(split("a sentence. " * 300))
    assert len(chunks) > 1 and all(
        len(text) <= 900 and end > start for text, start, end in chunks
    )
    with pytest.raises(ValueError):
        ingest(b"x" * (MAX_BYTES + 1), "large.txt")


def test_duplicate_and_isolation(service):
    a = service.user_collection("first")
    b = service.user_collection("second")
    assert not service.add(
        a, b"The fictional project launch code is AMBER-42.", "private.txt"
    )["duplicate"]
    assert service.add(
        a, b"The fictional project launch code is AMBER-42.", "private.txt"
    )["duplicate"]
    assert b.count() == 0
    assert "private.txt" not in [d["filename"] for d in service.documents("second")]
    result = service.query(
        "What is the fictional project launch code?", "first", "private.txt"
    )
    assert not result["abstained"] and "AMBER-42" in result["answer"]
    assert service.query(
        "What is the fictional project launch code?", "second", "private.txt"
    )["abstained"]


def test_citations_and_unknown(service):
    r = service.query("Who wrote the Zen of Python?", filename="zen-of-python.txt")
    assert (
        r["answer"] == "Tim Peters [1]"
        and r["answer"][:-4] in r["citations"][0]["passage"]
    )
    assert r["metrics"]["api_cost_usd"] == 0
    assert service.query("What is the capital of France?")["abstained"]


def test_api_errors_and_browser_isolation(service, monkeypatch):
    monkeypatch.setattr(main, "service", service)
    main.sessions.clear()
    a = TestClient(main.app)
    b = TestClient(main.app)
    assert a.get("/ready").status_code == 200
    assert a.post("/api/ask", json={"question": "x"}).status_code == 422
    assert (
        a.post("/api/ingest", files={"file": ("bad.pdf", b"broken")}).status_code == 400
    )
    assert (
        a.post(
            "/api/ingest",
            files={"file": ("ui.txt", b"A synthetic office is located in Lima.")},
        ).status_code
        == 200
    )
    assert "ui.txt" in [d["filename"] for d in a.get("/api/documents").json()]
    assert "ui.txt" not in [d["filename"] for d in b.get("/api/documents").json()]
    assert a.delete("/api/uploads").status_code == 200
    assert "ui.txt" not in [d["filename"] for d in a.get("/api/documents").json()]
    with service.lock:
        assert (
            a.post("/api/ask", json={"question": "Who wrote PEP 20?"}).status_code
            == 429
        )
    monkeypatch.setattr(main, "service", None)
    assert a.get("/ready").status_code == 503
    assert a.get("/health").json()["ready"] is False
