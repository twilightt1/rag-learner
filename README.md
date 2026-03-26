# RAG Learner

Ứng dụng trợ lý học tập dựa trên RAG (Retrieval-Augmented Generation) - upload tài liệu, hỏi đáp và tạo quiz.

## Tính năng

- **Upload tài liệu**: Hỗ trợ PDF, Markdown, URL và mã nguồn
- **Hỏi đáp thông minh**: Tìm kiếm ngữ nghĩa từ tài liệu và trả lời câu hỏi
- **Tạo quiz**: Tự động tạo câu hỏi trắc nghiệm và flashcard từ tài liệu
- **Lịch sử chat**: Lưu trữ và quản lý các phiên hỏi đáp

## Công nghệ

**Backend**: FastAPI, Python 3.11+, ChromaDB, SQLite (SQLModel), OpenRouter API
**Frontend**: React 18, Vite, TailwindCSS
**Models**: Embedding (`all-MiniLM-L6-v2`), Reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`), LLM (`google/gemma-3-27b-it:free`)

## Cài đặt nhanh

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # hoặc venv\Scripts\activate trên Windows
pip install -r requirements.txt
cp .env.example .env  # chỉnh sửa OPENROUTER_API_KEY nếu cần

# Frontend
cd ../frontend
npm install
```

## Chạy ứng dụng

```bash
# Terminal 1 - Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Truy cập: `http://localhost:5173`

## Kiểm thử

```bash
cd backend
pytest tests/ -x -q
```

## Cấu trúc project

```
rag-learner/
├── backend/           # FastAPI + logic RAG
│   ├── ingestion/    # Parse và chunk tài liệu
│   ├── rag/          # Embedding, vector store, retrieval
│   ├── llm/          # OpenRouter client, chat history
│   ├── quiz/         # Generator MCQ và flashcard
│   └── api/          # REST endpoints
├── frontend/          # React + TailwindCSS
├── data/              # ChromaDB, uploads, SQLite (gitignored)
```

## API chính

- `POST /api/ingest` - Upload file/URL
- `GET /api/documents` - Danh sách tài liệu
- `POST /api/chat` - Hỏi đáp
- `WS /api/chat/stream` - Stream phản hồi
- `POST /api/quiz/generate` - Tạo quiz từ tài liệu


Ứng dụng trợ lý học tập đơn người dùng, chạy hoàn toàn local.