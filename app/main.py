from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Dict
from qdrant_client import QdrantClient
from rag import ingest_documents, rag_answer
from rag import _qdrant, COLLECTION_NAME
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from fastapi.responses import RedirectResponse

app = FastAPI(title="RAG on Bedrock (JP)")

class Doc(BaseModel):
    id: str | None = None
    text: str = Field(..., description="日本語含む本文")

class IngestRequest(BaseModel):
    documents: List[Doc]

class AskRequest(BaseModel):
    query: str
    top_k: int = 5

@app.get("/")
def root():
    return RedirectResponse(url="/ui")

@app.post("/ingest")
def ingest(req: IngestRequest):
    result = ingest_documents([d.model_dump() for d in req.documents])
    return result

@app.post("/ask")
def ask(req: AskRequest):
    return rag_answer(req.query, top_k=req.top_k)

@app.get("/documents")
def list_documents():
    """
    Qdrant に保存されたドキュメント一覧を返す。
    doc_id 単位でまとめて返す。
    """
    try:
        # 全ポイントを取得する
        points, _ = _qdrant.scroll(
            collection_name=COLLECTION_NAME,
            limit=10000,
            with_payload=True
        )

        docs = {}
        for p in points:
            payload = p.payload
            doc_id = payload.get("doc_id")
            text = payload.get("text")
            chunk_id = payload.get("chunk_id")

            if not doc_id:
                continue

            if doc_id not in docs:
                docs[doc_id] = []

            docs[doc_id].append({
                "chunk_id": chunk_id,
                "text": text
            })

        return docs

    except Exception as e:
        return {"error": str(e)}

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    """
    doc_id で指定されたドキュメントを Qdrant から削除する
    """
    try:
        _qdrant.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id)
                    )
                ]
            )
        )
        return {"status": "deleted", "doc_id": doc_id}
    except Exception as e:
        return {"error": str(e)}

@app.post("/documents/{doc_id}/reingest")
def reingest_document(doc_id: str, body: dict):
    """
    doc_id の文書を削除 → 新しいテキストで再インデックス化
    body = {"text": "新しい内容"}
    """
    try:
        # まず削除
        delete_document(doc_id)

        # 再インデックス
        text = body.get("text")
        if not text:
            return {"error": "text is required"}

        from rag import ingest_documents
        result = ingest_documents([{"id": doc_id, "text": text}])
        return {"status": "reingested", "result": result}
    except Exception as e:
        return {"error": str(e)}
    
from ui import router as ui_router
app.include_router(ui_router)