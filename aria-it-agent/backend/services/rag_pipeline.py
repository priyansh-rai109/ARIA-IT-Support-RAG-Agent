import json
import hashlib
import requests
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from langchain_community.vectorstores import Chroma
from backend.config import GROQ_API_KEY, GROQ_MODEL, RERANK_MODEL_NAME
from backend.services.ingestion import get_vectorstore

# Global caches and indexes
semantic_cache = {}
bm25_index = None
bm25_docs = []
db_dirty = True
reranker_model = None

def get_reranker():
    global reranker_model
    if reranker_model is None:
        try:
            # Loads a highly efficient, CPU-friendly Cross-Encoder
            reranker_model = CrossEncoder(RERANK_MODEL_NAME)
        except Exception as e:
            print(f"Reranker download/load error, falling back to RRF: {e}")
            reranker_model = False
    return reranker_model

def notify_db_update():
    """Notifies the pipeline that the database has new files, requiring a BM25 rebuild."""
    global db_dirty
    db_dirty = True

def rebuild_bm25_index():
    """Rebuilds the BM25 lexical index by extracting all chunks from Chroma."""
    global bm25_index, bm25_docs, db_dirty
    try:
        vectorstore = get_vectorstore()
        # Fetch all stored documents from Chroma
        res = vectorstore.get()
        documents = res.get("documents", [])
        metadatas = res.get("metadatas", [])
        
        bm25_docs = []
        tokenized_corpus = []
        
        for idx, text in enumerate(documents):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            doc_info = {
                "content": text,
                "metadata": meta
            }
            bm25_docs.append(doc_info)
            # Basic tokenization
            tokenized_corpus.append(text.lower().split())
            
        if tokenized_corpus:
            bm25_index = BM25Okapi(tokenized_corpus)
        else:
            bm25_index = None
            
        db_dirty = False
        print(f"BM25 index successfully synchronized with Chroma. Total chunks indexed: {len(bm25_docs)}")
    except Exception as e:
        print(f"Error rebuilding BM25 index: {e}")
        bm25_index = None

def get_bm25_results(query: str, k: int = 5) -> list:
    """Performs BM25 lexical search against the indexed chunks."""
    global bm25_index, bm25_docs, db_dirty
    if db_dirty or bm25_index is None:
        rebuild_bm25_index()
    if bm25_index is None or not bm25_docs:
        return []
        
    query_tokens = query.lower().split()
    scores = bm25_index.get_scores(query_tokens)
    
    # Sort docs by score
    scored_docs = sorted(
        zip(range(len(scores)), scores),
        key=lambda x: x[1],
        reverse=True
    )
    
    results = []
    for idx, score in scored_docs[:k]:
        if score > 0.0:
            doc = bm25_docs[idx]
            results.append((doc["content"], doc["metadata"], score))
    return results

def expand_query(query: str) -> list:
    """Uses Groq to generate 3 diverse query variations to maximize recall."""
    if not GROQ_API_KEY:
        return [query]
        
    system_prompt = """You are an expert search engineering assistant. Rewrite the user's IT support question into 3 diverse, keyword-rich search queries optimized for a retrieval engine. Output ONLY a raw JSON list of strings. Do not explain anything.
Example output: ["vpn configuration globalprotect", "vpn connection failing globalprotect macOS", "how to install corporate VPN client"]"""
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant", # Rapid token execution
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Query: {query}"}
                ],
                "response_format": {"type": "json_object"}
            },
            timeout=5
        )
        if response.status_code == 200:
            res_content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "[]")
            expanded = json.loads(res_content)
            # Ensure it is a list
            if isinstance(expanded, dict):
                expanded = list(expanded.values())[0] if expanded else []
            if isinstance(expanded, list) and expanded:
                # Deduplicate and return
                return list(set([query] + expanded))
    except Exception as e:
        print(f"Error during query expansion: {e}")
        
    return [query]

def reciprocal_rank_fusion(vector_results, bm25_results, c=60):
    """Combines vector search and lexical search using Reciprocal Rank Fusion."""
    rrf_scores = {}
    
    # helper to identify unique chunk
    def get_chunk_id(content, metadata):
        # Fallback to hash of content if id is not in metadata
        return metadata.get("id", "") + "_" + hashlib.md5(content.encode("utf-8")).hexdigest()[:8]
    
    chunk_map = {}
    
    # Process vector results
    for rank, (content, metadata, score) in enumerate(vector_results):
        chunk_id = get_chunk_id(content, metadata)
        chunk_map[chunk_id] = (content, metadata)
        if chunk_id not in rrf_scores:
            rrf_scores[chunk_id] = 0.0
        rrf_scores[chunk_id] += 1.0 / (rank + 1 + c)
        
    # Process BM25 results
    for rank, (content, metadata, score) in enumerate(bm25_results):
        chunk_id = get_chunk_id(content, metadata)
        chunk_map[chunk_id] = (content, metadata)
        if chunk_id not in rrf_scores:
            rrf_scores[chunk_id] = 0.0
        rrf_scores[chunk_id] += 1.0 / (rank + 1 + c)
        
    # Sort by RRF score
    sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    fused_results = []
    for chunk_id, rrf_score in sorted_chunks:
        content, metadata = chunk_map[chunk_id]
        fused_results.append((content, metadata, rrf_score))
        
    return fused_results

def retrieve_hybrid_context(query: str, k: int = 5) -> tuple:
    """Executes the advanced multi-step retrieval pipeline (Expansion -> Hybrid Search -> RRF -> Rerank)."""
    # 1. Semantic Cache Check
    query_hash = hashlib.md5(query.lower().strip().encode("utf-8")).hexdigest()
    if query_hash in semantic_cache:
        print("Semantic cache hit! Returning cached context.")
        return semantic_cache[query_hash]
        
    # 2. Query Expansion
    expanded_queries = expand_query(query)
    print(f"Expanded queries: {expanded_queries}")
    
    all_vector_results = []
    all_bm25_results = []
    
    vectorstore = get_vectorstore()
    
    # 3. Retrieve chunks in parallel/loop for each expanded query
    for q in expanded_queries:
        # Vector semantic retrieval
        try:
            results = vectorstore.similarity_search_with_score(q, k=k)
            for doc, score in results:
                # Chroma HNWS score is distance (smaller = closer). Map to a rating.
                confidence = max(0.0, min(1.0, 1.0 - (score / 2.0)))
                all_vector_results.append((doc.page_content, doc.metadata, confidence))
        except Exception as e:
            print(f"Vector search failed for {q}: {e}")
            
        # BM25 lexical retrieval
        bm_res = get_bm25_results(q, k=k)
        all_bm25_results.extend(bm_res)
        
    # Remove duplicates inside vector/bm25 arrays while maintaining best score
    def deduplicate_raw_results(results):
        seen = {}
        for content, meta, score in results:
            key = meta.get("id", "") + "_" + content[:20]
            if key not in seen or score > seen[key][2]:
                seen[key] = (content, meta, score)
        return sorted(list(seen.values()), key=lambda x: x[2], reverse=True)
        
    dedup_vector = deduplicate_raw_results(all_vector_results)
    dedup_bm25 = deduplicate_raw_results(all_bm25_results)
    
    # 4. Reciprocal Rank Fusion (RRF)
    fused_results = reciprocal_rank_fusion(dedup_vector, dedup_bm25)
    
    # 5. Cross-Encoder Re-ranking
    reranker = get_reranker()
    reranked_results = []
    if reranker and fused_results:
        try:
            # Prepare query-doc pairs for cross-encoder evaluation
            pairs = [[query, content] for content, meta, score in fused_results]
            rerank_scores = reranker.predict(pairs)
            
            # Combine scores
            for idx, score in enumerate(rerank_scores):
                content, meta, rrf_score = fused_results[idx]
                # Convert logits to 0-1 sigmoid range if needed, or sort directly
                reranked_results.append((content, meta, float(score)))
                
            # Sort by rerank score
            reranked_results.sort(key=lambda x: x[2], reverse=True)
            print("Cross-Encoder successfully re-ranked fused results.")
        except Exception as rerank_err:
            print(f"Reranking execution failed: {rerank_err}")
            reranked_results = fused_results
    else:
        reranked_results = fused_results
        
    # 6. Truncate context & keep high confidence chunks (Rerank score > -3.0 or equivalent filters)
    final_chunks = []
    seen_titles = set()
    for content, metadata, score in reranked_results[:k]:
        # Filter duplicates or extremely low-relevance items
        final_chunks.append((content, metadata, score))
        
    # Construct context string & source listing
    context_parts = []
    sources = []
    for content, meta, score in final_chunks:
        context_parts.append(f"[{meta.get('title', 'Unknown Source')}]\n{content}")
        sources.append({
            "id": meta.get("id", ""),
            "title": meta.get("title", "Ingested Document"),
            "category": meta.get("category", "Support"),
            "pdf": meta.get("pdf", "")
        })
        
    context_text = "\n\n".join(context_parts)
    
    # Save cache
    semantic_cache[query_hash] = (context_text, sources)
    return context_text, sources
