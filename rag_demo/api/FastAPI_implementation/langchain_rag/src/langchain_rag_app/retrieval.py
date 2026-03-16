import math
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


@dataclass
class RetrievalCandidate:
    doc_id: str
    page: int
    content: str
    metadata: dict[str, Any]
    dense_rank: int | None = None
    bm25_rank: int | None = None
    dense_score: float | None = None
    bm25_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


@dataclass
class RerankResult:
    candidates: list[RetrievalCandidate]
    reranker_type: str
    latency_ms: float
    fallback_used: bool


def tokenize(text: str) -> list[str]:
    t = (text or "").lower()
    en = re.findall(r"[a-z0-9_]+", t)
    zh = re.findall(r"[\u4e00-\u9fff]", t)
    return en + zh


class BM25Index:
    def __init__(self, docs: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.tokenized = [tokenize(d.get("content", "")) for d in docs]
        self.doc_len = [len(toks) for toks in self.tokenized]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)

        df: dict[str, int] = {}
        for toks in self.tokenized:
            for tok in set(toks):
                df[tok] = df.get(tok, 0) + 1

        n = max(len(self.tokenized), 1)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

        self.tf = []
        for toks in self.tokenized:
            c: dict[str, int] = {}
            for tok in toks:
                c[tok] = c.get(tok, 0) + 1
            self.tf.append(c)

    def search(self, query: str, top_n: int = 20) -> list[tuple[float, dict[str, Any], int]]:
        q = tokenize(query)
        scored: list[tuple[float, dict[str, Any], int]] = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            dl = self.doc_len[i] if i < len(self.doc_len) else 0
            tf = self.tf[i]
            for term in q:
                if term not in tf:
                    continue
                f = tf[term]
                idf = self.idf.get(term, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * (dl / max(self.avgdl, 1e-9)))
                score += idf * (f * (self.k1 + 1)) / max(denom, 1e-9)
            scored.append((score, doc, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_n]


def rrf_fusion(
    dense_results: list[tuple[float, RetrievalCandidate]],
    bm25_results: list[tuple[float, RetrievalCandidate]],
    rrf_k: int = 60,
) -> list[RetrievalCandidate]:
    by_id: dict[str, RetrievalCandidate] = {}

    for rank, (score, c) in enumerate(dense_results, start=1):
        cur = by_id.get(c.doc_id, c)
        cur.dense_rank = rank
        cur.dense_score = score
        cur.fusion_score = (cur.fusion_score or 0.0) + 1.0 / (rrf_k + rank)
        by_id[c.doc_id] = cur

    for rank, (score, c) in enumerate(bm25_results, start=1):
        cur = by_id.get(c.doc_id, c)
        cur.bm25_rank = rank
        cur.bm25_score = score
        cur.fusion_score = (cur.fusion_score or 0.0) + 1.0 / (rrf_k + rank)
        by_id[c.doc_id] = cur

    out = list(by_id.values())
    out.sort(key=lambda x: x.fusion_score or 0.0, reverse=True)
    return out


def _extract_years(text: str) -> set[str]:
    return set(re.findall(r"\b(19\d{2}|20\d{2}|11[0-9])\b", text or ""))


def heuristic_rerank(
    query: str,
    candidates: list[RetrievalCandidate],
    top_k: int,
    candidate_pool: int,
    year_bonus: float = 0.1,
) -> list[RetrievalCandidate]:
    q_toks = set(tokenize(query))
    q_years = _extract_years(query)
    pool = candidates[:candidate_pool]

    rescored = []
    for c in pool:
        d_toks = set(tokenize(c.content))
        overlap = len(q_toks & d_toks) / max(len(q_toks), 1)
        y_bonus = year_bonus if (q_years and q_years & _extract_years(c.content)) else 0.0
        base = c.fusion_score or 0.0
        c.rerank_score = base + overlap + y_bonus
        rescored.append(c)

    rescored.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
    return rescored[:top_k]


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str, device: str):
    from sentence_transformers import CrossEncoder  # lazy import

    return CrossEncoder(model_name, device=device)


def cross_encoder_rerank(
    query: str,
    candidates: list[RetrievalCandidate],
    top_k: int,
    candidate_pool: int,
    model_name: str,
    batch_size: int,
    max_length: int,
    device: str,
) -> list[RetrievalCandidate]:
    pool = candidates[: min(candidate_pool, 100)]
    model = _load_cross_encoder(model_name, device)
    pairs = [(query, c.content[: max_length * 4]) for c in pool]
    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)

    rescored = []
    for c, s in zip(pool, scores):
        c.rerank_score = float(s)
        rescored.append(c)

    rescored.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
    return rescored[:top_k]


def rerank_candidates(query: str, candidates: list[RetrievalCandidate], cfg: dict[str, Any]) -> RerankResult:
    rerank_cfg = cfg.get("rerank", {})
    r_type = (rerank_cfg.get("type") or "heuristic").lower()
    top_k = int(rerank_cfg.get("top_k", cfg.get("k", 5)))
    candidate_pool = int(rerank_cfg.get("candidate_pool", 30))

    start = time.perf_counter()
    fallback_used = False

    if r_type == "none":
        out = candidates[:top_k]
        return RerankResult(out, "none", (time.perf_counter() - start) * 1000.0, False)

    if r_type == "cross_encoder":
        ce = rerank_cfg.get("cross_encoder", {})
        try:
            ranked = cross_encoder_rerank(
                query=query,
                candidates=candidates,
                top_k=top_k,
                candidate_pool=candidate_pool,
                model_name=ce.get("model_name", "BAAI/bge-reranker-v2-m3"),
                batch_size=int(ce.get("batch_size", 16)),
                max_length=int(ce.get("max_length", 512)),
                device=ce.get("device", "cpu"),
            )
        except Exception:
            fallback_used = True
            h = rerank_cfg.get("heuristic", {})
            ranked = heuristic_rerank(
                query, candidates, top_k=top_k, candidate_pool=candidate_pool, year_bonus=float(h.get("year_bonus", 0.1))
            )
            r_type = "cross_encoder_fallback_heuristic"
    else:
        h = rerank_cfg.get("heuristic", {})
        ranked = heuristic_rerank(
            query,
            candidates,
            top_k=top_k,
            candidate_pool=candidate_pool,
            year_bonus=float(h.get("year_bonus", 0.1)),
        )

    # 保底：rerank top (k-2) + fusion top 2
    if top_k >= 3:
        primary = ranked[: max(top_k - 2, 1)]
        backup = candidates[:2]
        seen = set()
        merged: list[RetrievalCandidate] = []
        for c in primary + backup:
            if c.doc_id in seen:
                continue
            seen.add(c.doc_id)
            merged.append(c)
        ranked = merged[:top_k]

    latency_ms = (time.perf_counter() - start) * 1000.0
    return RerankResult(ranked, r_type, latency_ms, fallback_used)
