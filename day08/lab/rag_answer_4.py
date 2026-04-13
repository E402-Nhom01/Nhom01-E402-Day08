"""
RAG Pipeline — Sprint 4 (Final Optimized Version)
Key upgrades:
✓ Hybrid retrieval (dense + BM25 + Weighted RRF)
✓ Cross-encoder rerank (with global cache)
✓ Strong anti-hallucination prompt
✓ Smart exponential backoff for Gemini rate limits
✓ Fixed compatibility with eval.py
"""

import os
import json
import time
import random
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

# ========================= CONFIG =========================
TOP_K_SEARCH = 20
TOP_K_SELECT = 6
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Global cache for expensive reranker model
_cross_encoder_model = None


# =============================================================================
# DENSE RETRIEVAL
# =============================================================================
def retrieve_dense(query: str, top_k: int) -> List[Dict]:
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

    retrieved = []
    for d, m, dist in zip(docs, metas, dists):
        score = 1 - float(dist)
        if score > 0.3:
            retrieved.append({
                "text": d,
                "metadata": m,
                "score": score
            })
    return retrieved


# =============================================================================
# SPARSE RETRIEVAL (BM25)
# =============================================================================
def retrieve_sparse(query: str, top_k: int) -> List[Dict]:
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
        {
            "text": docs[i],
            "metadata": metas[i],
            "score": float(scores[i])
        }
        for i in top_idx
    ]


# =============================================================================
# HYBRID RETRIEVAL (Weighted Reciprocal Rank Fusion)
# =============================================================================
def retrieve_hybrid(query: str, top_k: int) -> List[Dict]:
    dense = retrieve_dense(query, top_k * 2)   # Get more candidates for better fusion
    sparse = retrieve_sparse(query, top_k * 2)

    scores = {}

    # Weighted RRF
    for rank, d in enumerate(dense):
        scores[d["text"]] = scores.get(d["text"], 0) + 0.6 * (1 / (60 + rank))

    for rank, s in enumerate(sparse):
        scores[s["text"]] = scores.get(s["text"], 0) + 0.4 * (1 / (60 + rank))

    # Merge - prefer dense metadata when collision
    merged = {}
    for item in dense + sparse:
        text = item["text"]
        if text not in merged or item.get("score", 0) > merged[text].get("score", 0):
            merged[text] = item

    # Sort by fused score
    ranked = sorted(
        merged.values(),
        key=lambda x: scores.get(x["text"], 0),
        reverse=True
    )

    return ranked[:top_k]


# =============================================================================
# RERANK (Cross-Encoder) - WITH GLOBAL CACHE
# =============================================================================
def rerank(query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
    global _cross_encoder_model

    from sentence_transformers import CrossEncoder

    # Load model only once
    if _cross_encoder_model is None:
        print(f"Loading reranker model: {RERANKER_MODEL} (first time only)...")
        _cross_encoder_model = CrossEncoder(RERANKER_MODEL, device="cpu")

    model = _cross_encoder_model

    pairs = [[query, c["text"]] for c in candidates]
    scores = model.predict(pairs)

    # Combine candidates with new reranker scores
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

    result = []
    for c, score in ranked[:top_k]:
        c = c.copy()                    # Avoid mutating original
        c["score"] = float(score)       # Update score with reranker score
        result.append(c)

    return result


# =============================================================================
# CONTEXT BUILDER
# =============================================================================
def build_context(chunks: List[Dict]) -> str:
    parts = []

    for i, c in enumerate(chunks, 1):
        meta = c["metadata"]
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        department = meta.get("department", "")
        effective_date = meta.get("effective_date", "")
        score = c.get("score", 0.0)

        header = f"[{i}] {source}"
        if section:
            header += f" | Section: {section}"
        if department:
            header += f" | Dept: {department}"
        if effective_date and effective_date != "unknown":
            header += f" | Effective: {effective_date}"
        header += f" | score={score:.3f}"

        parts.append(f"{header}\n{c['text']}")

    return "\n\n".join(parts)


# =============================================================================
# ANTI-HALLUCINATION PROMPT
# =============================================================================
def build_prompt(query, context):
    return f"""You MUST answer ONLY using the provided context below.

STRICT GROUNDING RULES:
- Use ONLY information explicitly stated in the context. DO NOT use outside knowledge.
- Every claim MUST have a citation like [1], [2]. No citation possible → abstain.
- If the answer is NOT clearly supported → say EXACTLY: "Không đủ dữ liệu trong tài liệu để trả lời."

TEMPORAL & VERSION REASONING:
- Each chunk has metadata: Source, Section, Department, Effective Date.
- When the question asks about changes or history → compare version info within the context.
- When the question involves a specific date → check Effective Date metadata to determine which policy version applies.
- Always cite the Effective Date or version number when answering time-sensitive questions.

CROSS-DOCUMENT SYNTHESIS:
- If chunks come from DIFFERENT sources (different Source fields), synthesize information from ALL relevant sources.
- Cite EACH source separately: e.g., "VPN là bắt buộc [1] và giới hạn 2 thiết bị [3]."
- Do NOT answer from only one source if the question requires information from multiple documents.

COMPLETENESS & EXCEPTIONS:
- When listing conditions or exceptions → scan the ENTIRE context and list ALL matching items, not just the first one found.
- If the question mentions multiple conditions (e.g., "Flash Sale VÀ đã kích hoạt") → verify EACH condition against the exception list and address EVERY one explicitly.
- For "có ... không?" questions → check ALL exception/exclusion clauses before concluding. If MULTIPLE exceptions apply, list each one with its own citation.
- NEVER stop after finding one matching exception. Always check if there are more.

SCOPE & ELIGIBILITY:
- Before answering "có thể ... không?" questions → FIRST check the SCOPE section (phạm vi áp dụng) to determine WHO the policy applies to (nhân viên, contractor, third-party vendor, etc.).
- Then answer the specific details (approver, timeline, requirements) based on the relevant level/category.
- If scope information exists in context, always mention it.

DISAMBIGUATION:
- If the same number/term appears in different contexts (e.g., "3 ngày" in leave policy vs sick leave vs access revocation) → clearly distinguish each usage and its specific context.

ABSTAIN RULES:
- If the context does not contain the SPECIFIC information asked → abstain. Do NOT infer from general knowledge.
- CRITICAL: If the question asks about penalties, fines, compensation amounts, or consequences that are NOT explicitly written in context → you MUST say "Không đủ dữ liệu trong tài liệu để trả lời." Do NOT guess or infer penalty amounts from the existence of SLA/policy documents.
- Having a related document (e.g., SLA document) does NOT mean the answer is in it. Only answer what is EXPLICITLY stated.
- Partial match is NOT enough. The context must directly support the answer.

OUTPUT FORMAT:
- Answer in Vietnamese.
- Include citations [1], [2] directly after supporting statements.
- Use bullet points when listing multiple items.
- Be concise and factual.

Question: {query}

Context:
{context}

Answer:"""


# =============================================================================
# LLM CALL - SMART RATE LIMIT HANDLING
# =============================================================================
def call_llm(prompt: str, max_retries: int = 5) -> str:
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
            return res.text.strip() if res.text else "Không đủ dữ liệu trong tài liệu để trả lời."

        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(kw in error_str for kw in ["429", "resource_exhausted", "rate limit", "quota"])

            if is_rate_limit:
                if attempt == max_retries - 1:
                    print(f"Rate limit persisted after {max_retries} attempts.")
                    break

                base_delay = (2 ** attempt) * 2
                jitter = random.uniform(0, 3)
                wait_time = min(base_delay + jitter, 60)

                print(f"Rate limit hit (attempt {attempt+1}). Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"LLM error: {e}")
                break

    return "Không đủ dữ liệu trong tài liệu để trả lời."


def _generate_reasoning(query: str, answer: str, chunks: List[Dict]) -> str:
    """LLM tự đánh giá câu trả lời và giải thích lý do."""
    chunk_summaries = []
    for i, c in enumerate(chunks, 1):
        src = c["metadata"].get("source", "?")
        sec = c["metadata"].get("section", "")
        score = c.get("score", 0.0)
        preview = c["text"][:150].replace("\n", " ")
        chunk_summaries.append(f"[{i}] {src} | {sec} | score={score:.3f}\n    {preview}...")

    eval_prompt = f"""Bạn là evaluator cho hệ thống RAG. Hãy đánh giá câu trả lời dưới đây.

Câu hỏi: {query}

Câu trả lời: {answer}

Chunks đã retrieve:
{chr(10).join(chunk_summaries)}

Hãy trả lời NGẮN GỌN (3-5 dòng) theo format:
- Faithfulness: (1-5) — Câu trả lời có bám sát context không? Có bịa thêm không?
- Relevance: (1-5) — Câu trả lời có đúng trọng tâm câu hỏi không?
- Completeness: (1-5) — Có thiếu thông tin quan trọng nào trong context không?
- Lý do: 1-2 câu giải thích ngắn gọn tại sao cho điểm như vậy."""

    return call_llm(eval_prompt)


# =============================================================================
# MAIN RAG PIPELINE
# =============================================================================
def rag_answer_4(
    query: str,
    retrieval_mode: str = "hybrid",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = True,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Main RAG pipeline function.
    Returns consistent format for both manual testing and eval.py
    """

    # 1. Retrieval
    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k_search)
    else:  # hybrid (default)
        candidates = retrieve_hybrid(query, top_k_search)

    # 2. Rerank (optional)
    if use_rerank and candidates:
        selected = rerank(query, candidates, top_k_select)
    else:
        selected = candidates[:top_k_select]

    # 3. Build prompt
    context = build_context(selected)
    prompt = build_prompt(query, context)

    if verbose:
        print("\n--- CONTEXT ---\n", context[:800] + "..." if len(context) > 800 else context)
        print("\n--- PROMPT (first 700 chars) ---\n", prompt[:700] + "...\n")

    # 4. Generate answer
    answer = call_llm(prompt)

    sources = list({c["metadata"].get("source", "unknown") for c in selected})

    # 5. Generate reasoning — tại sao trả lời như vậy
    reasoning = _generate_reasoning(query, answer, selected)

    # 6. Append sources + scores + reasoning after answer
    source_lines = []
    for i, c in enumerate(selected, 1):
        src = c["metadata"].get("source", "unknown")
        sec = c["metadata"].get("section", "")
        score = c.get("score", 0.0)
        line = f"  [{i}] {src}"
        if sec:
            line += f" | {sec}"
        line += f" (score: {score:.3f})"
        source_lines.append(line)

    answer_with_sources = (
        f"{answer}\n\n"
        f"--- Sources ---\n"
        + "\n".join(source_lines)
        + f"\n\n--- Reasoning ---\n{reasoning}"
    )

    return {
        "query": query,
        "answer": answer_with_sources,
        "answer_raw": answer,
        "reasoning": reasoning,
        "chunks_used": selected,
        "sources": sources,
    }


# =============================================================================
# TEST QUERIES (for quick manual testing)
# =============================================================================
test_queries = [
    ("baseline_1", "SLA xử lý ticket P1 là bao lâu?"),
    ("baseline_2", "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?"),
    ("gq01", "SLA P1 thay đổi thế nào so với phiên bản trước?"),
    ("gq03", "Flash Sale + đã kích hoạt → hoàn tiền không?"),
]


# =============================================================================
# QUICK EVALUATION HELPER
# =============================================================================
def run_full_evaluation():
    from datetime import datetime

    RESULT_PATH = Path(__file__).parent / "data" / "result.json"

    print("\n" + "="*90)
    print("FULL EVALUATION - TEST QUERIES")
    print("="*90)

    all_results = []

    for i, (qid, query) in enumerate(test_queries, 1):
        print(f"\n[{i:02d}/{len(test_queries)}] [{qid}] {query}")

        result = rag_answer_4(query, verbose=False)

        print(f"Answer : {result['answer']}")
        print(f"Sources: {result['sources']}")
        print(f"Chunks : {len(result['chunks_used'])}")

        # Log result
        all_results.append({
            "id": qid,
            "query": query,
            "answer": result["answer_raw"],
            "reasoning": result.get("reasoning", ""),
            "sources": result["sources"],
            "chunks_used": [
                {
                    "source": c["metadata"].get("source", ""),
                    "section": c["metadata"].get("section", ""),
                    "score": round(c.get("score", 0), 4),
                    "text_preview": c["text"][:200],
                }
                for c in result["chunks_used"]
            ],
        })

        if i < len(test_queries):
            time.sleep(2.0)

    # Save to data/result.json
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "config": {
            "retrieval_mode": "hybrid",
            "top_k_search": TOP_K_SEARCH,
            "top_k_select": TOP_K_SELECT,
            "use_rerank": True,
        },
        "results": all_results,
    }

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "="*90)
    print(f"EVALUATION COMPLETED — saved to {RESULT_PATH}")
    print("="*90)


if __name__ == "__main__":
    run_full_evaluation()
