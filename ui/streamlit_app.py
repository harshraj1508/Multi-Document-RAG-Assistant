"""Streamlit UI for the RAG assistant.

A single-page app: log in, pick a namespace, upload documents, and chat.
It talks to the FastAPI backend over HTTP.
"""
import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Generous timeout: ingesting + chatting runs embeddings and an LLM call, which
# can take longer than httpx's default 5s read timeout (especially the first
# request, which loads the embedding model).
TIMEOUT = 180

st.set_page_config(page_title="RAG Assistant", page_icon="📄")
st.title("📄 Multi-Document RAG Assistant")

# --- session state ---
st.session_state.setdefault("token", None)
st.session_state.setdefault("session_id", None)
st.session_state.setdefault("messages", [])


def auth_header() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


@st.cache_data(ttl=30, show_spinner=False)
def fetch_documents(token: str, namespace: str) -> list[dict]:
    """Cached document list.

    Streamlit reruns the whole script on every interaction, so without caching
    we'd call the API on every keystroke. The cache (keyed by token+namespace)
    avoids redundant calls; it's cleared after an upload or delete.
    """
    r = httpx.get(
        f"{API_URL}/documents",
        headers={"Authorization": f"Bearer {token}"},
        params={"namespace": namespace},
        timeout=TIMEOUT,
    )
    return r.json() if r.status_code == 200 else []


# --- Sidebar: auth + documents ---
with st.sidebar:
    st.header("Account")
    if st.session_state.token is None:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        col1, col2 = st.columns(2)
        if col1.button("Register"):
            r = httpx.post(
                f"{API_URL}/auth/register",
                json={"email": email, "password": password},
                timeout=TIMEOUT,
            )
            if r.status_code == 201:
                st.success("Registered! Now click Login.")
            else:
                st.error(r.text)
        if col2.button("Login"):
            r = httpx.post(
                f"{API_URL}/auth/login",
                data={"username": email, "password": password},
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                st.session_state.token = r.json()["access_token"]
                st.rerun()
            else:
                st.error("Login failed")
    else:
        st.success("Logged in")
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.header("Documents")
    namespace = st.text_input("Namespace", value="default")

    if st.session_state.token:
        uploaded = st.file_uploader("Upload a .txt/.md file", type=["txt", "md"])
        if uploaded and st.button("Ingest"):
            with st.spinner("Ingesting (embedding chunks)..."):
                r = httpx.post(
                    f"{API_URL}/documents",
                    headers=auth_header(),
                    files={"file": (uploaded.name, uploaded.getvalue())},
                    data={"namespace": namespace},
                    timeout=TIMEOUT,
                )
            if r.status_code == 201:
                fetch_documents.clear()  # refresh the cached list
                st.success(f"Ingested ({r.json()['chunk_count']} chunks)")
            else:
                st.error(r.text)

        if st.button("Refresh list"):
            fetch_documents.clear()

        for d in fetch_documents(st.session_state.token, namespace):
            c1, c2 = st.columns([4, 1])
            c1.write(f"📄 {d['filename']} ({d['chunk_count']})")
            if c2.button("🗑", key=f"del{d['id']}"):
                httpx.delete(
                    f"{API_URL}/documents/{d['id']}",
                    headers=auth_header(),
                    timeout=TIMEOUT,
                )
                fetch_documents.clear()
                st.rerun()


# --- Main: chat ---
if st.session_state.token is None:
    st.info("Log in from the sidebar to begin.")
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if question := st.chat_input("Ask a question about your documents..."):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            r = httpx.post(
                f"{API_URL}/chat",
                headers=auth_header(),
                json={
                    "question": question,
                    "namespace": namespace,
                    "session_id": st.session_state.session_id,
                },
                timeout=TIMEOUT,
            )
            if r.status_code == 200:
                data = r.json()
                st.session_state.session_id = data["session_id"]
                st.write(data["answer"])
                if data["citations"]:
                    st.caption(
                        f"✅ Answer generated by Groq LLM, grounded in "
                        f"{len(data['citations'])} source chunk(s) from "
                        f"namespace '{namespace}'."
                    )
                    with st.expander("📎 Citations (sources this answer is based on)"):
                        for c in data["citations"]:
                            st.caption(f"**{c['filename']}** — chunk #{c['chunk_index']}")
                            st.text(c["snippet"])
                else:
                    st.caption(f"ℹ️ No matching content in namespace '{namespace}'.")
                st.session_state.messages.append(
                    {"role": "assistant", "content": data["answer"]}
                )
            else:
                st.error(r.text)
