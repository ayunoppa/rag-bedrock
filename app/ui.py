from fastapi import APIRouter, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from rag import ingest_documents
from utils import split_into_chunks
import fitz  # PyMuPDF
import markdown
import re
import requests
import json

router = APIRouter()

# Docker環境では 'api' が自分自身を指す
BACKEND_URL = "http://api:8000/ingest"


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """PDFからテキスト抽出"""
    text = ""
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text


def extract_text_from_md(file_bytes: bytes) -> str:
    """Markdownをプレーンテキスト化"""
    text = file_bytes.decode("utf-8")
    html = markdown.markdown(text)
    return re.sub(r"<[^>]*>", "", html)


@router.post("/upload")
async def upload_file(file: UploadFile):
    """PDF/MD/TXT をアップロードして安全に ingest_documents に渡す"""
    content = await file.read()
    ext = file.filename.lower()

    if ext.endswith(".pdf"):
        text = extract_text_from_pdf(content)
    elif ext.endswith(".md") or ext.endswith(".markdown"):
        text = extract_text_from_md(content)
    elif ext.endswith(".txt"):
        text = content.decode("utf-8")
    else:
        return JSONResponse({"error": "対応していないファイル形式です。"}, status_code=400)

    # ❗ Titan に渡す前にチャンク分割（巨大文字列を防ぐ）
    chunks = split_into_chunks(text, max_chars=800)

    if not chunks:
        return JSONResponse({"error": "抽出テキストが空でした"}, status_code=400)

    # ingest_documents() に複数チャンクを渡す
    documents = [{"id": f"{file.filename}_{i}", "text": chunk}
                 for i, chunk in enumerate(chunks)]

    try:
        result = ingest_documents(documents)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.get("/ui", response_class=HTMLResponse)
async def ui_page():
    return """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>RAG 管理UI</title>
        <style>
            body { font-family: sans-serif; background-color: #f9fafb; margin: 40px; }
            h1 { color: #333; }
            textarea { width: 100%; height: 100px; padding: 8px; font-size: 14px; }
            button { margin-top: 10px; padding: 10px 20px; font-size: 14px; cursor: pointer; }
            pre { background-color: #fff; padding: 15px; border-radius: 6px; white-space: pre-wrap; }
            .upload-box, .docs-box {
                margin-top: 30px; padding: 20px; border-radius: 10px; background-color: #fff;
                box-shadow: 0 0 6px rgba(0,0,0,0.1);
            }
            .doc-item {
                padding: 6px 0; border-bottom: 1px solid #ddd;
                display: flex; justify-content: space-between; align-items: center;
            }
            .doc-item:last-child { border-bottom: none; }
            .btn-del {
                background-color: #e74c3c; color: white; border: none;
                padding: 5px 10px; cursor: pointer; border-radius: 6px;
            }
        </style>
    </head>
    <body>
        <h1>📚 RAG 日本語 管理UI</h1>

        <!-- 質問欄 -->
        <textarea id="query" placeholder="質問を入力してください（例：RAGとは何？）"></textarea><br>
        <button type="button" onclick="ask()">送信</button>
        <h3>回答</h3>
        <pre id="answer"></pre>

        <!-- ファイルアップロード -->
        <div class="upload-box">
            <h3>📂 ファイルをアップロードして知識登録</h3>
            <input type="file" id="fileInput" accept=".pdf,.txt,.md,.markdown">
            <button type="button" onclick="upload()">アップロード</button>
            <pre id="uploadResult"></pre>
        </div>

        <!-- ドキュメント一覧 -->
        <div class="docs-box">
            <h3>📁 登録済みドキュメント一覧</h3>
            <div id="docs"></div>
        </div>

        <script>
        async function ask() {
            const query = document.getElementById("query").value;
            const res = await fetch("/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ query })
            });
            const data = await res.json();
            document.getElementById("answer").innerText =
                data.answer || "エラーが発生しました";
        }

        async function upload() {
            const file = document.getElementById("fileInput").files[0];
            if (!file) { alert("ファイルを選択してください"); return; }

            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch("/upload", { method: "POST", body: formData });
            const data = await res.json();
            document.getElementById("uploadResult").innerText =
                JSON.stringify(data, null, 2);

            loadDocs();
        }

        async function loadDocs() {
            const res = await fetch("/documents");
            const docs = await res.json();

            const box = document.getElementById("docs");
            box.innerHTML = "";

            Object.keys(docs).forEach(doc_id => {
                const div = document.createElement("div");
                div.className = "doc-item";
                div.innerHTML = `
                    <span>${doc_id}</span>
                    <button class="btn-del" onclick="delDoc('${doc_id}')">削除</button>
                `;
                box.appendChild(div);
            });
        }

        async function delDoc(doc_id) {
            if (!confirm(doc_id + " を削除しますか？")) return;

            await fetch("/documents/" + doc_id, { method: "DELETE" });
            loadDocs();
        }

        window.onload = loadDocs;
        </script>
    </body>
    </html>
    """
