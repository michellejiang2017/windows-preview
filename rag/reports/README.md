# Verified deployment and evaluation

Live Python backend and browser UI: https://passage-document-qa.onrender.com

Measured against the public free Render service on 2026-10-13 UTC, deployed from commit `aa08550`. Subsequent formatting and documentation changes do not change model/retrieval behavior. Raw results are in `evaluation-cloud.json` and `evaluation-local.json`.

| Check | Result |
|---|---:|
| Expected source retrieved within top four | 10/10 |
| Normalized exact answer, answerable questions | 7/10 |
| Correct refusal, unrelated questions | 2/2 |
| Mean answer token F1 | 0.713 |
| Returned answer is an exact span in cited passage | 100% |
| Cloud median / p95 wall-clock latency | 0.354 / 2.386 s |
| Inference API spend for evaluation | $0 |
| Local peak observed process RSS | 269.1 MB |

The three answer failures are PEP 20 creation date, PEP 20 title and the synthetic PDF secret value. Their source passages were retrieved, but the similarity gate refused to answer. This separates retrieval success from answer success; 100% citation span containment is not 100% answer accuracy. The 12 visible fixtures are deliberately small and do not demonstrate performance on unseen customer documents. P95 uses linear interpolation over the 12 recorded observations; it is not a stable service-level measurement. Cold-start latency and cloud RSS are not included.

Eleven Python tests passed locally and on GitHub Linux. Local and public Chrome browser checks passed for answering with citations, PDF/text uploads, CSV drag-and-drop, malformed PDF errors, upload removal and mobile layout. Existing Preview web build/test and public deployment checks passed. The public service was verified through `/ready`, the question API, and the browser workflow; a successful deployment status alone was not treated as proof.

The free plan was explicitly selected at $0/month. API cost measures inference vendor spend, not a guarantee of unlimited free hosting. No paid API keys, agents, or managed database subscriptions were added. Uploaded passages are temporary; authenticated storage, OCR ingestion, multi-passage summaries, CSV aggregation and production availability are not implemented.
