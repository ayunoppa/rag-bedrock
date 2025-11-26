import os
import json
import uuid
from typing import List, Dict, Optional, Tuple

import boto3
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from utils import split_into_chunks

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
BEDROCK_EMBED_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
BEDROCK_LLM_MODEL_ID = os.getenv("BEDROCK_LLM_MODEL_ID", "anthropic.claude-3-5-sonnet-20240620-v1:0")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "docs_jp")
EMBED_DIM = 1024  # Titan v2 既定（切替も可）

# Bedrock Runtime client
_bedrock_rt = boto3.client("bedrock-runtime", region_name=AWS_REGION)

# Qdrant client
_qdrant = QdrantClient(url=QDRANT_URL)

def ensure_collection():
    existing = [c.name for c in _qdrant.get_collections().collections]
    if COLLECTION_NAME not in existing:
        _qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

def _sanitize_and_rechunk(texts: list[str], max_len: int = 8000) -> list[str]:
    import re
    out = []
    for t in texts:
        if not isinstance(t, str):
            t = str(t)
        # 制御文字を除去
        t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", t)
        t = t.strip()
        if not t:
            continue
        # 8,000文字ごとに分割
        for i in range(0, len(t), max_len):
            seg = t[i:i+max_len].strip()
            if seg:
                out.append(seg)
    return out

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Amazon Titan Text Embeddings v2 の正しい呼び出し + 安全化
    """
    # ★ 追加：安全化＆再分割
    texts = _sanitize_and_rechunk(texts, max_len=8000)
    if not texts:
        raise RuntimeError("No valid text to embed after sanitization")

    # Titan v2 は inputText / inputTextList を受け取る
    payload = {"inputText": texts[0]} if len(texts) == 1 else {"inputTextList": texts}

    response = _bedrock_rt.invoke_model(
        modelId=BEDROCK_EMBED_MODEL_ID,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    body = response["body"].read()
    result = json.loads(body)

    if "embedding" in result:
        vectors = [result["embedding"]]
    elif "embeddingList" in result:
        vectors = [v["embedding"] for v in result["embeddingList"]]
    else:
        raise RuntimeError(f"Titan API unexpected response: {result}")

    return np.array(vectors, dtype=np.float32)

def ingest_documents(documents: List[Dict[str, str]]) -> Dict:
    """
    documents: [{"id": "doc1", "text": "..."}, ...]
    """
    ensure_collection()
    points: List[PointStruct] = []
    for doc in documents:
        doc_id = doc.get("id") or str(uuid.uuid4())
        text = doc.get("text", "")
        if not text.strip():
            continue
        chunks = split_into_chunks(text, max_chars=800)
        vecs = embed_texts(chunks)
        for i, (chunk, vec) in enumerate(zip(chunks, vecs)):
            pid = str(uuid.uuid4())  # ← ここで一意のUUIDを自動生成
            points.append(PointStruct(
                id=pid,
                vector=vec.tolist(),
                payload={"doc_id": doc_id, "chunk_id": i, "text": chunk}
            ))
    if points:
        _qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
    return {"indexed_points": len(points)}

def search(query: str, top_k: int = 5) -> List[Dict]:
    ensure_collection()
    qvec = embed_texts([query])[0]
    res = _qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=qvec.tolist(),
        limit=top_k,
        with_payload=True
    )
    hits = []
    for r in res:
        payload = r.payload or {}
        hits.append({
            "score": float(r.score),
            "text": payload.get("text", ""),
            "doc_id": payload.get("doc_id"),
            "chunk_id": payload.get("chunk_id")
        })
    return hits

def build_prompt(contexts: List[str], user_query: str) -> Tuple[str, Dict]:
    """
    Claude 3.5 Sonnet へ渡す system + messages（日本語）
    """
    system = (
        "あなたは日本語のアシスタントです。以下のコンテキストに厳密に基づき、"
        "根拠を示しながら簡潔に回答してください。わからない場合は無理に推測せず「不明」と答えてください。"
        "必要に応じて箇条書きで。"
    )
    context_block = "\n\n".join([f"- {c}" for c in contexts])
    user = f"ユーザー質問:\n{user_query}\n\n参照コンテキスト:\n{context_block}"

    # ClaudeのConverse相当のpayload（InvokeModelでもフォーマットOK）
    message = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.2,
        "system": system,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user}]}
        ]
    }
    return user, message

def generate_with_bedrock_claude(message_payload: Dict) -> str:
    resp = _bedrock_rt.invoke_model(
        modelId=BEDROCK_LLM_MODEL_ID,
        body=json.dumps(message_payload).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    out = json.loads(resp["body"].read())
    # Anthropic形式: content: [{type:"text", text:"..."}]
    contents = out.get("content", [])
    texts = [c.get("text", "") for c in contents if c.get("type") == "text"]
    return "\n".join(texts).strip()

def rag_answer(query: str, top_k: int = 5) -> Dict:
    hits = search(query, top_k=top_k)
    contexts = [h["text"] for h in hits]
    _, payload = build_prompt(contexts, query)
    answer = generate_with_bedrock_claude(payload)
    return {
        "answer": answer,
        "contexts": hits
    }

