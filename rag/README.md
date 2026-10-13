# Passage: free document Q&A

A separate Python RAG application in Windows Preview. The existing desktop and web editors keep their local/offline behavior. PDF ingestion reuses `desktop.engine.Document` read-only; no Qt dependency or editor state changes.

## Run locally

Use Python 3.12 from the repository root (not from `rag/`):

```powershell
py -3.12 -m venv rag/.venv
rag/.venv/Scripts/python -m pip install -r rag/requirements.txt
rag/.venv/Scripts/python -m rag.app.bootstrap
rag/.venv/Scripts/python -m uvicorn rag.app.main:app --host 127.0.0.1 --port 8000
```

Linux/macOS: use `python3.12`, then `rag/.venv/bin/python`. Open http://127.0.0.1:8000. `/health` reports process health; `/ready` returns 503 until the models/index are ready. `/docs` documents the API. First bootstrap downloads two public models with pinned revisions in `model_manifest.json`. Model files and uploaded data are ignored by Git. No keys or paid inference services are required.

## Architecture and decisions

Browser → FastAPI → read-only PDF/text/CSV extraction → overlapping passages with page/row metadata → quantized MiniLM sentence embeddings → Chroma cosine vector search → quantized DistilBERT extracts an exact span → source passage citation.

- MiniLM embeddings are attention-weighted mean-pooled and normalized, computed with ONNX Runtime and tokenizers directly. Avoiding PyTorch keeps this small enough for the free host.
- Passages are at most 900 characters with 120-character overlap. Text and PDF page boundaries retain attribution. CSV records are one passage each; explicit row requests use metadata filtering. Source selection filters by filename. Chroma stores the vectors, passages and metadata.
- Retrieve top four passages, read up to three with extractive QA, choose the span by QA confidence times similarity. Similarity below .24 or combined score below .012 results in abstention. These are heuristics; confidence is not calibrated probability of correctness. The SQuAD model was not trained for unanswerable questions. Refusals and mistaken spans remain possible.
- This is extractive RAG, not an LLM generating a summary. It does not combine facts across passages or perform CSV arithmetic. The answer is always an exact substring of the first cited passage. Exact containment does not prove that a passage answers the question.
- Sample documents are public and provenance/checksums are in `sample_sources.json`. The PDF includes a synthetic scanned page that is skipped; it does not silently claim OCR support.
- Random HTTP-only session cookies isolate uploads into separate collections. Twenty active sessions maximum, 1,500 passages each, 20 API calls per minute per session, one model operation at a time. Uploads are limited to 5 MB, 150 PDF pages, 500 CSV rows and 150,000 text characters. A session can remove its uploads. Collections expire after an hour of inactivity on a subsequent request, or on restart. This is bounded demo isolation, not authenticated multi-tenant security; cookie renewal can bypass per-session rate limiting.

## Free Render deployment

`render.yaml` describes a single free Python service. Select this repository, Python 3, branch main, leave root directory empty, and choose **Free** explicitly (the dashboard may default to a paid plan).

Build: `pip install -r rag/requirements.txt && python -m rag.app.bootstrap`

Start: `uvicorn rag.app.main:app --host 0.0.0.0 --port $PORT --workers 1`

Set `PYTHON_VERSION=3.12.10`. Health-check `/health`. Build-time bootstrap downloads the pinned models and indexes samples. Startup readiness protects requests while models load. No database subscription or API secret is needed.

Render free instances sleep after 15 minutes idle and have ephemeral storage. Uploads vanish on redeploy/restart; public samples rebuild. Shared workspace free hours can run out, especially with another active service. There is no availability guarantee. See https://render.com/docs/free. This is an interview/demo deployment, not production-grade.

## Tests and evaluation

```powershell
rag/.venv/Scripts/python -m pytest rag/tests -q
rag/.venv/Scripts/python -m rag.app.evaluate --output rag/reports/evaluation-local.json
rag/.venv/Scripts/python -m rag.app.evaluate --url https://YOUR-SERVICE.onrender.com --output rag/reports/evaluation-cloud.json
```

`eval/questions.json` contains 12 public fixture questions (10 answerable, 2 unrelated). Reports record every answer and failure, retrieval hit@4, normalized exact accuracy, token F1, abstention, exact citation containment, wall-clock median/p95 latency and zero inference API spend. Local RSS is sampled after each question, not a continuous memory profiler. Cloud latency includes the network; cloud memory is not measured by the client. Cost is API spend only, not total infrastructure cost if the plan changes. One small visible set cannot establish general performance; avoid describing this as 100% accurate based on citation containment. Reports are reproducible snapshots, not a benchmark tuned to guarantee success.

Tests cover extraction metadata, malformed inputs, duplicate indexing, upload isolation, exact citations, unavailable index, clearing uploads and busy responses. The original Preview editors are not modified.

## Interview explanation

“I built a document-answering prototype under a zero-budget constraint. I reused the existing PDF reader, stored 384-dimensional sentence vectors in Chroma, and chose quantized extractive QA to stay within 512 MB without a paid API. Citations point to the exact passage and original page or CSV row. I measured retrieval separately from answers, so I could see when the right context was found but the confidence gate refused an answer. Upload isolation, explicit readiness and size limits make failures understandable. For a real customer, I would first identify their documents and success criteria, then evaluate a held-out set, calibrate abstention, and add authenticated storage and monitoring.”

Next meaningful work would be a customer-specific corpus and held-out evaluation, improved identifier retrieval/confidence calibration, and durable authenticated storage. OCR remains in the existing Preview editor; it is not integrated into this service. No agents or 3D functionality are involved.
