"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3

def _get_embedding_fn():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(text: str) -> list:
        return model.encode(text).tolist()

    return embed
def _get_collection():
    import chromadb
    import os

    # Go from: workers/ → project root
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "chroma_db")

    print("📦 Using DB path:", DB_PATH)  # debug

    client = chromadb.PersistentClient(path=DB_PATH)

    try:
        collection = client.get_collection("day09_docs")
        print("✅ Collection loaded. Total docs:", collection.count())
    except Exception:
        collection = client.get_or_create_collection(
            "day09_docs",
            metadata={"hnsw:space": "cosine"}
        )
        print("⚠️ Collection exists but empty. Please re-index.")

    return collection

def _keyword_overlap_score(query: str, text: str) -> float:
    q_words = set(query.lower().split())
    t_words = set(text.lower().split())
    return len(q_words & t_words) / (len(q_words) + 1e-5)

def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval with safe scoring + fallback handling
    """
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )

        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        chunks = []

        for doc, dist, meta in zip(documents, distances, metadatas):
            if not doc:
                continue

            # ✅ safer similarity conversion
            dense_score = 1 / (1 + dist) if dist is not None else 0.0
            keyword_score = _keyword_overlap_score(query, doc)

            # hybrid
            score = 0.7 * dense_score + 0.3 * keyword_score

            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown") if meta else "unknown",
                "score": round(score, 4),
                "metadata": meta or {},
            })

        # ✅ sort by score descending
        chunks = sorted(chunks, key=lambda x: x["score"], reverse=True)

        # ✅ deduplicate (same text)
        seen = set()
        unique_chunks = []
        for c in chunks:
            if c["text"] not in seen:
                unique_chunks.append(c)
                seen.add(c["text"])

        return unique_chunks[:top_k]

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        return []


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)
        retrieval_confidence = (
            sum(c["score"] for c in chunks) / len(chunks)
            if chunks else 0.0
        )

        state["retrieval_confidence"] = round(retrieval_confidence, 4)

        # ✅ fallback signal
        if not chunks:
            state["history"].append(f"[{WORKER_NAME}] no results → possible retrieval failure")

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")

        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
