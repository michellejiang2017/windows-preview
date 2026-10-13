"""Two quantized, public models. No inference API, PyTorch, agents, or API keys."""

import json, os
from pathlib import Path
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def model_files():
    manifest = json.loads((ROOT / "model_manifest.json").read_text())
    paths = {}
    for name, info in manifest.items():
        folder = ROOT / "models" / name
        for file in ["tokenizer.json", info["file"]]:
            hf_hub_download(
                info["repo"], filename=file, revision=info["revision"], local_dir=folder
            )
        paths[name] = (folder / "tokenizer.json", folder / info["file"])
    return paths


def session(path):
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    return ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])


def tensors(tokenizer, texts, pairs=None):
    encoded = tokenizer.encode_batch(
        texts if pairs is None else list(zip(texts, pairs))
    )
    inputs = {
        "input_ids": np.array([e.ids for e in encoded], dtype=np.int64),
        "attention_mask": np.array([e.attention_mask for e in encoded], dtype=np.int64),
        "token_type_ids": np.array([e.type_ids for e in encoded], dtype=np.int64),
    }
    return encoded, inputs


class Models:
    def __init__(self):
        paths = model_files()
        self.embedding = session(paths["embedding"][1])
        self.answering = session(paths["answer"][1])
        self.embed_tokenizer = Tokenizer.from_file(str(paths["embedding"][0]))
        self.qa_tokenizer = Tokenizer.from_file(str(paths["answer"][0]))
        self.embed_tokenizer.enable_truncation(max_length=256)
        self.embed_tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        self.qa_tokenizer.enable_truncation(max_length=384, strategy="only_second")
        self.qa_tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

    def embed(self, texts):
        result = []
        for offset in range(0, len(texts), 8):
            _, inputs = tensors(self.embed_tokenizer, texts[offset : offset + 8])
            names = {x.name for x in self.embedding.get_inputs()}
            hidden = self.embedding.run(
                None, {k: v for k, v in inputs.items() if k in names}
            )[0]
            mask = inputs["attention_mask"][..., None]
            pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1).clip(1)
            pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(1e-12)
            result.extend(pooled.astype(np.float32).tolist())
        return result

    def extract(self, question, context):
        encoded, inputs = tensors(self.qa_tokenizer, [question], [context])
        names = {x.name for x in self.answering.get_inputs()}
        start, end = self.answering.run(
            None, {k: v for k, v in inputs.items() if k in names}
        )[:2]
        e = encoded[0]
        valid = [
            i
            for i, sequence in enumerate(e.sequence_ids)
            if sequence == 1 and e.offsets[i][1] > e.offsets[i][0]
        ]
        best = None
        for a in valid:
            for b in valid:
                if b < a or b - a > 32:
                    continue
                score = float(start[0, a] + end[0, b])
                if best is None or score > best[0]:
                    best = (score, a, b)
        if best is None:
            return "", 0.0
        _, a, b = best
        answer = context[e.offsets[a][0] : e.offsets[b][1]].strip()
        s = np.exp(start[0] - start[0].max())
        t = np.exp(end[0] - end[0].max())
        confidence = float(s[a] / s.sum() * t[b] / t.sum())
        return answer, confidence
