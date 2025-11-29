# 🚀 Bedrock RAG System（日本語対応 / PDFアップロード / 管理UI付き）

このプロジェクトは **Amazon Bedrock（Claude 3.5 + Titan Embeddings v2） × FastAPI × Qdrant × Docker Compose** を利用した  
**日本語対応 RAG（検索拡張生成）システム** です。

PDF / TXT / Markdown のアップロード → 自動テキスト抽出 → 分割 → 埋め込み → Qdrant 保存  
Claude 3.5 による質問応答  
アップロード済みナレッジの一覧表示・削除・再学習ができる管理 UI  
に対応しています。

Web UI は以下でアクセスできます：

```
http://localhost:8000/
```

---

## 📚 RAG の処理フロー

### 学習フェーズ（ドキュメント登録時）

1. PDF / TXT / Markdown をアップロード  
2. テキストを抽出  
3. 本文をチャンクに分割  
4. 各チャンクを **Titan Embeddings v2** でベクトル化  
5. ベクトル（およびチャンク情報）を **Qdrant** に保存

### 回答フェーズ（質問時）

1. ユーザーの質問を受け付け  
2. 質問文を **Titan Embeddings v2** でベクトル化  
3. Qdrant による類似検索で関連チャンクを取得  
4. 取得したチャンクをコンテキストとして **Claude 3.5** に渡す  
5. Claude が “質問 + コンテキスト” をもとに**回答を生成**  
6. 回答を返す  

---

# 🔐 1. AWS アクセスキーの発行方法

1. https://console.aws.amazon.com/iam/  
2. 左メニュー「ユーザー」を選択  
3. 対象の IAM ユーザーをクリック  
4. 「セキュリティ認証情報」タブを開く  
5. 「アクセスキー」セクション → アクセスキーを作成  
6. 用途は CLI を選択  
7. 以下を控える  
   - AWS Access Key ID  
   - AWS Secret Access Key  

※ アクセスキーは絶対に GitHub にコミットしないこと。

---

# 💻 2. AWS CLI のインストール（WSL / Linux）

```
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

確認：

```
aws --version
```

---

# 🔧 3. AWS CLI の設定

```
aws configure
```

入力例：

```
AWS Access Key ID: AKIAxxxxxxxx
AWS Secret Access Key: xxxxxxxxxxxxx
Default region name: ap-northeast-1
Default output format: json
```

設定ファイル：

- ~/.aws/credentials  
- ~/.aws/config

---

# 🐳 4. Docker / Docker Compose の準備

WSL（Ubuntu）の場合：

```
sudo apt update
sudo apt install docker.io docker-compose-plugin -y
sudo service docker start
```

---

# 📁 5. プロジェクト構成

```
rag-bedrock/
├── docker-compose.yml
├── .env
└── app/
    ├── Dockerfile
    ├── main.py
    ├── rag.py
    ├── utils.py
    ├── ui.py
    ├── requirements.txt
```

---

# ⚙ 6. `.env` の設定

```
AWS_REGION=ap-northeast-1
AWS_PROFILE=default

BEDROCK_LLM_MODEL_ID=anthropic.claude-3-5-sonnet-20240620-v1:0
BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
```

※ `.env` は Git にコミットしないこと。

---

# 🐳 7. docker-compose.yml

※ コミット対象のため README には記載しません。

---

# 🛠 8. Docker ビルド & 起動

```
docker compose build --no-cache
docker compose up -d
```

Web UI 起動確認：

```
http://localhost:8000/
```

---

# 🌐 9. Web UI の機能

- Claude 3.5 への質問  
- PDF / TXT / Markdown のアップロード  
- 自動テキスト抽出 → チャンク分割 → 埋め込み  
- Qdrant への保存  
- 登録済みドキュメント一覧  
- ドキュメント削除  
- 再インデックス化（re-ingest）

---

# 🧠 10. RAG API（curl）

## 文書追加（ingest）

```
curl -X POST http://localhost:8000/ingest   -H "Content-Type: application/json"   -d '{"documents":[{"id":"doc1","text":"RAGとは…"}]}'
```

## 質問（ask）

```
curl -X POST http://localhost:8000/ask   -H "Content-Type: application/json"   -d '{"query":"RAGとは？"}'
```

## 登録済みドキュメント一覧

```
curl http://localhost:8000/documents
```

## ドキュメント削除

```
curl -X DELETE http://localhost:8000/documents/<doc_id>
```

## 再学習（reingest）

```
curl -X POST http://localhost:8000/documents/<doc_id>/reingest   -H "Content-Type: application/json"   -d '{"text":"新しい内容"}'
```

---

# 🧰 11. 利用技術

- FastAPI  
- Amazon Bedrock（Claude 3.5 / Titan Embeddings v2）  
- Qdrant（Vector DB）  
- Docker Compose  
- PyMuPDF（PDF抽出）  
- HTML + JavaScript（Web UI）

---

# 🚀 12. 運用コマンド

## 起動

```
docker compose up -d
```

## 停止

```
docker compose down
```

## 再ビルド（コード変更時）

```
docker compose build --no-cache
docker compose up -d
```

---

# 🎉 13. 完成

この README の手順に従えば以下が構築できます：

- AWS 認証設定  
- Docker 環境  
- Bedrock × FastAPI × Qdrant の完全な RAG 基盤  
- PDF/TXT/MD のアップロード → 自動インデックス化  
- `/` で管理 UI 表示  
- 登録済みナレッジの一覧表示・削除・再学習

RAG アプリケーションの開発・運用をすぐ開始できます。
