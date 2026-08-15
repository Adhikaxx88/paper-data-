# Chatbot

`chatbot/app.py`

## How to use the chatbot

1. Make sure the batch pipeline has been run at least once (`python
   run_pipeline.py`), so there's indexed content to retrieve from.
2. Start the app:

   ```bash
   streamlit run chatbot/app.py
   ```

3. Open the printed URL (default `http://localhost:8501`).
4. Type a question about the scraped news topics (e.g. "Apa aturan terbaru
   OJK soal pinjol?") into the chat input at the bottom and press Enter.
5. The assistant's answer appears in the chat, grounded in the retrieved
   articles. Below each answer is a **"Sumber artikel"** (source articles)
   expander — click it to see which articles (title, source, date) were
   used to generate that answer.

## Screenshot

![Chatbot screenshot placeholder](https://via.placeholder.com/800x500?text=News+RAG+Chatbot+Screenshot)

*(Replace with an actual screenshot of the running app.)*

## Session persistence

On first load, the app generates a random `session_id` (UUID) and stores it
in `st.session_state.session_id`. Every question/answer pair sent through
that session is saved to PostgreSQL's `chat_messages` table under that id,
and the last 10 messages are fed back into the LLM as conversation history
for follow-up questions (see [RAG Pipeline](rag/pipeline.md)).

This session id lives only for the browser tab's Streamlit session — reload
or open the app in a new tab and a new `session_id` (and therefore a fresh
conversation) is created. The full history remains queryable in PostgreSQL
by `session_id` even after the UI session ends.
