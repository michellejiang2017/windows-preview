import hashlib, json, os, re, time, threading
from pathlib import Path

os.environ.setdefault("OTEL_SDK_DISABLED", "true")
import chromadb
from chromadb.config import Settings
from .models import Models, ROOT
from .ingestion import ingest


class RagService:
    def __init__(self, data_dir=None):
        self.models = Models()
        self.db = chromadb.PersistentClient(
            path=str(data_dir or ROOT / "data"),
            settings=Settings(anonymized_telemetry=False),
        )
        self.lock = threading.Lock()
        self.samples = self.collection("samples")
        self.seed()

    def collection(self, name):
        return self.db.get_or_create_collection(
            name, metadata={"hnsw:space": "cosine"}, embedding_function=None
        )

    def user_collection(self, session):
        return self.collection(
            "user_" + hashlib.sha256(session.encode()).hexdigest()[:32]
        )

    def add(self, collection, data, filename, url=""):
        chunks = ingest(data, filename, url)
        digest = chunks[0].metadata["doc_id"]
        existing = collection.get(where={"doc_id": digest}, include=[])
        if existing["ids"]:
            return {
                "filename": filename,
                "chunks": len(existing["ids"]),
                "duplicate": True,
            }
        if collection.count() + len(chunks) > 1500:
            raise ValueError(
                "This session reached the passage limit. Start a new session or use a smaller document."
            )
        vectors = self.models.embed([c.text for c in chunks])
        collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
            embeddings=vectors,
        )
        return {"filename": filename, "chunks": len(chunks), "duplicate": False}

    def seed(self):
        for item in json.loads((ROOT / "sample_sources.json").read_text()):
            self.add(
                self.samples,
                (ROOT / "samples" / item["file"]).read_bytes(),
                item["file"],
                item["url"],
            )

    def documents(self, session=None):
        docs = {}
        for name, collection in [("samples", self.samples)] + (
            [("uploads", self.user_collection(session))] if session else []
        ):
            for meta in collection.get(include=["metadatas"])["metadatas"]:
                key = (name, meta["doc_id"])
                entry = docs.setdefault(
                    key,
                    {
                        "filename": meta["filename"],
                        "scope": name,
                        "source_url": meta["source_url"],
                        "chunks": 0,
                    },
                )
                entry["chunks"] += 1
        return list(docs.values())

    def query(self, question, session=None, filename=None, k=4):
        started = time.perf_counter()
        vector = self.models.embed([question])[0]
        filters = []
        if filename:
            filters.append({"filename": filename})
        row = re.search(r"\b(?:data\s+)?row\s+(\d+)\b", question, re.I)
        if row:
            filters.append({"row": int(row.group(1))})
        where = (
            {"$and": filters} if len(filters) > 1 else filters[0] if filters else None
        )
        candidates = []
        for collection in [self.samples] + (
            [self.user_collection(session)] if session else []
        ):
            if not collection.count():
                continue
            result = collection.query(
                query_embeddings=[vector],
                n_results=min(k, collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            for id, text, meta, distance in zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ):
                candidates.append(
                    {
                        "id": id,
                        "passage": text,
                        **meta,
                        "similarity": round(1 - float(distance), 4),
                    }
                )
        candidates = sorted(candidates, key=lambda c: c["similarity"], reverse=True)[:k]
        retrieval_ms = (time.perf_counter() - started) * 1000
        best = None
        calls = 0
        if candidates and candidates[0]["similarity"] >= 0.24:
            for n, item in enumerate(candidates[:3]):
                answer, confidence = self.models.extract(question, item["passage"])
                calls += 1
                score = confidence * max(0, item["similarity"])
                if answer and (best is None or score > best[0]):
                    best = (score, n, answer, confidence)
        supported = bool(best and best[0] >= 0.012)
        if supported:
            _, n, answer, confidence = best
            winner = candidates.pop(n)
            candidates.insert(0, winner)
            answer += " [1]"
        else:
            answer = "I could not find a supported answer in the available documents."
            confidence = 0.0
        for n, item in enumerate(candidates, 1):
            item["citation"] = n
            item["used_for_answer"] = supported and n == 1
        return {
            "answer": answer,
            "abstained": not supported,
            "citations": candidates,
            "confidence": round(confidence, 4),
            "metrics": {
                "retrieval_ms": round(retrieval_ms, 2),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "api_cost_usd": 0.0,
                "model_calls": calls,
            },
            "answer_method": "extractive neural QA; not generative chat",
        }
