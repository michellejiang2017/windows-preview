"""A small transparent fixture evaluation, not a general benchmark."""

import argparse, json, re, time, statistics, platform
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import httpx, psutil
from .models import ROOT


def normalize(text):
    return re.findall(r"\w+", text.lower())


def f1(predicted, expected):
    p = normalize(predicted)
    e = normalize(expected)
    common = sum((Counter(p) & Counter(e)).values())
    return 2 * common / (len(p) + len(e)) if p and e else float(p == e)


def run(url=None):
    cases = json.loads((ROOT / "eval/questions.json").read_text())
    results = []
    latencies = []
    rss = []
    if url:
        client = httpx.Client(
            base_url=url.rstrip("/"), timeout=180, follow_redirects=True
        )
        client.get("/ready").raise_for_status()
    else:
        from .service import RagService

        svc = RagService()
    for case in cases:
        start = time.perf_counter()
        if url:
            response = client.post(
                "/api/ask",
                json={"question": case["question"], "filename": case.get("filename")},
            )
            response.raise_for_status()
            answer = response.json()
        else:
            answer = svc.query(case["question"], filename=case.get("filename"))
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)
        rss.append(psutil.Process().memory_info().rss / 1048576)
        predicted = answer["answer"].removesuffix(" [1]")
        expected = case["answers"]
        unknown = case.get("unanswerable", False)
        retrieved = (
            any(
                case.get("source_contains", "\x00") in c["passage"]
                and c["filename"] == case.get("filename")
                for c in answer["citations"]
            )
            if not unknown
            else None
        )
        correct = (
            answer["abstained"]
            if unknown
            else not answer["abstained"]
            and any(normalize(predicted) == normalize(e) for e in expected)
        )
        citation_supported = answer["abstained"] or bool(
            answer["citations"]
            and predicted in answer["citations"][0]["passage"]
            and answer["citations"][0]["used_for_answer"]
        )
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected": expected,
                "answer": predicted,
                "abstained": answer["abstained"],
                "retrieval_hit_at_4": retrieved,
                "exact_correct": correct,
                "token_f1": max(
                    (f1(predicted, e) for e in expected), default=float(correct)
                ),
                "citation_span_supported": citation_supported,
                "latency_ms": round(elapsed, 2),
                "server_latency_ms": answer["metrics"]["latency_ms"],
                "api_cost_usd": answer["metrics"]["api_cost_usd"],
            }
        )
    positives = [r for r in results if r["retrieval_hit_at_4"] is not None]
    unknowns = [r for r in results if r["retrieval_hit_at_4"] is None]
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": url or "local direct service",
        "machine": platform.platform(),
        "scope": "12 public fixture questions; not a hidden/general benchmark. Latency is one warm sequential run, including the first query; cloud includes network. Citation support checks exact span containment, not semantic correctness. CSV row metadata and filename filters are part of retrieval.",
        "summary": {
            "questions": len(results),
            "retrieval_hit_at_4": sum(r["retrieval_hit_at_4"] for r in positives)
            / len(positives),
            "answer_exact_accuracy": sum(r["exact_correct"] for r in positives)
            / len(positives),
            "mean_token_f1": statistics.mean(r["token_f1"] for r in positives),
            "unknown_abstention_accuracy": sum(r["exact_correct"] for r in unknowns)
            / len(unknowns),
            "citation_span_support_rate": statistics.mean(
                r["citation_span_supported"] for r in results
            ),
            "latency_median_ms": round(statistics.median(latencies), 2),
            "latency_p95_ms": round(
                statistics.quantiles(latencies, n=100, method="inclusive")[94], 2
            ),
            "inference_api_cost_usd": sum(r["api_cost_usd"] for r in results),
            "peak_observed_local_rss_mb": round(max(rss), 1) if not url else None,
        },
        "results": results,
    }
    if url:
        client.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--output", default=str(ROOT / "reports/local-evaluation.json"))
    args = parser.parse_args()
    report = run(args.url)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    print("Report:", path)
