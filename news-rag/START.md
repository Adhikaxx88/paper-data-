## Quick Start

1. Start Docker services (PostgreSQL and Qdrant; the LLMs run on OpenRouter):
   docker compose up -d postgres qdrant

2. Start backend:
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload

3. Start frontend (dev):
   cd frontend
   npm install
   npm run dev

4. Open http://localhost:5173 (dev) or http://localhost:5888 (Docker)

## .env additions needed:
OPENROUTER_API_KEY=your-openrouter-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DATASET_GENERATOR_MODEL=openai/gpt-4o-mini
RAG_GENERATOR_MODEL=deepseek/deepseek-chat-v3-0324
JUDGE_MODEL=google/gemini-2.5-flash
GUARDRAIL_MODEL=openai/gpt-4o-mini
