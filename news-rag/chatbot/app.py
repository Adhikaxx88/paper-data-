"""Streamlit chat interface for the news RAG chatbot."""
import os
import sys
import uuid

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.pipeline import ask  # noqa: E402

st.set_page_config(page_title="News RAG Chatbot", page_icon="📰")
st.title("📰 News RAG Chatbot")

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4()
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("sources"):
            with st.expander("Sumber artikel"):
                for source in message["sources"]:
                    st.markdown(f"**{source['title']}** — {source['source']} ({source['date']})")

question = st.chat_input("Tanyakan sesuatu tentang berita...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Mencari jawaban..."):
            result = ask(question, st.session_state.session_id)
        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander("Sumber artikel"):
                for source in result["sources"]:
                    st.markdown(f"**{source['title']}** — {source['source']} ({source['date']})")

    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
