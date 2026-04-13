"""
RAG Pipeline — Sprint 4 (Final Optimized Version)

Key upgrades:
✓ Hybrid retrieval (dense + BM25)
✓ Cross-encoder rerank (cached)
✓ Strong anti-hallucination prompt
✓ Smart exponential backoff for Gemini rate limits
"""

import os
import time
import random
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

# ========================= CONFIG =========================
TOP_K_SEARCH = 20
TOP_K_SELECT = 5
retrieval_mode = "hybrid"
use_rerank = True
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Global cache for expensive reranker model
_cross_encoder_model = None


# =============================================================================
# DENSE RETRIEVAL
# =============================================================================
def retrieve_dense(query: str, top_k: int):
    import chromadb
    from index import get_embedding, CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    emb = get_embedding(query)

    results = collection.query(
        query_embeddings=[emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]

    return [
        {"text": d, "metadata": m, "score": 1 - dist}
        for d, m, dist in zip(docs, metas, dists)
    ]


# =============================================================================
# SPARSE RETRIEVAL (BM25)
# =============================================================================
def retrieve_sparse(query: str, top_k: int):
    import chromadb
    from rank_bm25 import BM25Okapi
    from index import CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    data = collection.get(include=["documents", "metadatas"])
    docs = data["documents"]
    metas = data["metadatas"]

    tokenized = [doc.lower().split() for doc in docs]
    bm25 = BM25Okapi(tokenized)

    scores = bm25.get_scores(query.lower().split())

    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    return [
        {"text": docs[i], "metadata": metas[i], "score": float(scores[i])}
        for i in top_idx
    ]


# =============================================================================
# HYBRID RETRIEVAL (Weighted RRF)
# =============================================================================
def retrieve_hybrid(query: str, top_k: int):
    dense = retrieve_dense(query, top_k)
    sparse = retrieve_sparse(query, top_k)

    scores = {}

    # Weighted Reciprocal Rank Fusion
    for rank, d in enumerate(dense):
        scores[d["text"]] = scores.get(d["text"], 0) + 0.6 * (1 / (60 + rank))

    for rank, s in enumerate(sparse):
        scores[s["text"]] = scores.get(s["text"], 0) + 0.4 * (1 / (60 + rank))

    # Merge (prefer dense metadata on collision)
    merged = {item["text"]: item for item in dense + sparse}

    ranked = sorted(
        merged.values(),
        key=lambda x: scores.get(x["text"], 0),
        reverse=True
    )

    return ranked[:top_k]


# =============================================================================
# RERANK (Cross-Encoder) - WITH GLOBAL CACHE
# =============================================================================
def rerank(query: str, candidates: List[Dict], top_k: int):
    global _cross_encoder_model

    from sentence_transformers import CrossEncoder

    # Load model only once and cache it
    if _cross_encoder_model is None:
        print(f"Loading reranker model: {RERANKER_MODEL} (this may take a moment first time)...")
        _cross_encoder_model = CrossEncoder(RERANKER_MODEL)

    model = _cross_encoder_model

    pairs = [[query, c["text"]] for c in candidates]
    scores = model.predict(pairs)

    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    return [c for c, _ in ranked[:top_k]]


# =============================================================================
# CONTEXT BUILDER
# =============================================================================
def build_context(chunks: List[Dict]):
    parts = []

    for i, c in enumerate(chunks, 1):
        meta = c["metadata"]
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = c.get("score", 0.0)

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        header += f" | score={score:.2f}"

        parts.append(f"{header}\n{c['text']}")

    return "\n\n".join(parts)


# =============================================================================
# ANTI-HALLUCINATION PROMPT
# =============================================================================
def build_prompt(query, context):
    return f"""
You MUST answer ONLY using the provided context.

STRICT RULES:
- If the answer is NOT explicitly in the context → say EXACTLY:
  "Không đủ dữ liệu trong tài liệu để trả lời."
- DO NOT guess or use outside knowledge.
- Every answer MUST include at least one citation like [1].
- If you cannot cite → abstain.

REASONING RULES:
- If multiple conditions exist → verify ALL conditions.
- If any condition is missing → abstain.
- If multiple pieces of info are needed → use bullet points.
- If numbers are present → return exact values.
- If multiple versions exist → compare them.
- If time/date matters → reason about applicability.

Question: {query}

Context:
{context}

Answer:
"""

# =============================================================================
# LLM CALL - SMART RATE LIMIT HANDLING
# =============================================================================
def call_llm(prompt: str, max_retries: int = 5):
    import google.generativeai as genai

    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    for attempt in range(max_retries):
        try:
            res = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 1024
                }
            )
            return res.text.strip() if res.text else "Không đủ dữ liệu"

        except Exception as e:
            error_str = str(e).lower()

            is_rate_limit = any(kw in error_str for kw in ["429", "resource_exhausted", "rate limit", "quota"])

            if is_rate_limit:
                if attempt == max_retries - 1:
                    print(f"Rate limit persisted after {max_retries} attempts.")
                    break

                # Exponential backoff + jitter
                base_delay = (2 ** attempt) * 2          # 2s, 4s, 8s, 16s...
                jitter = random.uniform(0, 3)
                wait_time = min(base_delay + jitter, 60)

                print(f"Rate limit hit (attempt {attempt+1}/{max_retries}). "
                      f"Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
                continue

            else:
                # Other errors
                print(f"LLM error: {e}")
                break

    return "Không đủ dữ liệu"


# =============================================================================
# MAIN RAG PIPELINE
# =============================================================================
def rag_answer(query: str, verbose=False):
    # 1. Hybrid Retrieval
    candidates = retrieve_hybrid(query, TOP_K_SEARCH)

    # 2. Rerank
    selected = rerank(query, candidates, TOP_K_SELECT)

    # 3. Build prompt
    context = build_context(selected)
    prompt = build_prompt(query, context)

    if verbose:
        print("\n--- PROMPT (first 700 chars) ---\n", prompt[:700] + "...\n")

    # 4. Generate answer
    answer = call_llm(prompt)

    sources = list({c["metadata"].get("source", "unknown") for c in selected})

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "selected_chunks": len(selected)
    }


# =============================================================================
# TEST QUERIES
# =============================================================================
test_queries = [
    ("baseline_1", "SLA xử lý ticket P1 là bao lâu?"),
    ("baseline_2", "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"),
    ("baseline_3", "Ai phải phê duyệt để cấp quyền Level 3?"),
    ("baseline_4", "ERR-403-AUTH là lỗi gì?"),

    ("gq01", "SLA P1 thay đổi thế nào so với phiên bản trước?"),
    ("gq02", "Remote + VPN + giới hạn thiết bị?"),
    ("gq03", "Flash Sale + đã kích hoạt → hoàn tiền không?"),
    ("gq04", "Store credit được bao nhiêu %?"),
    ("gq05", "Contractor cần Admin Access — điều kiện?"),
    ("gq06", "P1 lúc 2am → cấp quyền tạm thời thế nào?"),
    ("gq07", "Mức phạt vi phạm SLA P1 là bao nhiêu?"),
    ("gq08", "Báo nghỉ phép 3 ngày = nghỉ ốm 3 ngày không?"),
    ("gq09", "Mật khẩu đổi mấy ngày, nhắc trước mấy ngày?"),
    ("gq10", "Chính sách v4 áp dụng đơn trước 01/02 không?"),
]


# =============================================================================
# EVALUATION
# =============================================================================
def run_full_evaluation():
    print("\n" + "="*90)
    print("FULL EVALUATION - 10 QUESTIONS")
    print("="*90)

    results = []

    for i, (qid, query) in enumerate(test_queries, 1):
        print(f"\n[{i:02d}/{len(test_queries)}] [{qid}] {query}")

        result = rag_answer(query, verbose=False)

        print(f"Answer : {result['answer']}")
        print(f"Sources: {result['sources']}")
        print(f"Chunks : {result['selected_chunks']}")

        results.append({
            "id": qid,
            "query": query,
            "answer": result["answer"],
            "sources": result["sources"]
        })

        # Gentle pacing to reduce rate limit pressure
        if i < len(test_queries):
            time.sleep(2.0)

    print("\n" + "="*90)
    print("EVALUATION COMPLETED")
    print("="*90)
    return results


if __name__ == "__main__":
    # Uncomment to test single query with full prompt visible:
    # result = rag_answer("SLA xử lý ticket P1 là bao lâu?", verbose=True)
    # print("\nFinal Answer:", result["answer"])

    # Run full evaluation
    run_full_evaluation()