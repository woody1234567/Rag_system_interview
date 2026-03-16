import math
from typing import Any

from ..core import get_embeddings


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def compute_similarity_diagnostics(answer: str, gold: str, question: str, evidence: str, enabled: bool = True) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False, "ans_gold_sim": None, "ans_q_sim": None, "ans_evidence_sim": None}

    emb = get_embeddings()
    vecs = emb.embed_documents([answer or "", gold or "", question or "", evidence or ""])
    ans, gd, q, ev = vecs
    return {
        "enabled": True,
        "ans_gold_sim": round(_cosine(ans, gd), 4),
        "ans_q_sim": round(_cosine(ans, q), 4),
        "ans_evidence_sim": round(_cosine(ans, ev), 4),
    }
