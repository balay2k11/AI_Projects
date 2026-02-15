import os, json
import numpy as np
import faiss
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in .env")

client = OpenAI(api_key=API_KEY)

INDEX_DIR = "index"
FAISS_PATH = os.path.join(INDEX_DIR, "docs.faiss")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

@st.cache_resource(show_spinner=False)
def load_index_and_meta():
    if not os.path.exists(FAISS_PATH) or not os.path.exists(META_PATH):
        return None, None
    index = faiss.read_index(FAISS_PATH)
    with open(META_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return index, meta

def embed_query(q: str) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=q)
    v = np.array(resp.data[0].embedding, dtype="float32").reshape(1, -1)
    faiss.normalize_L2(v)
    return v

def retrieve(index, meta, q: str, k: int = 5):
    qv = embed_query(q)
    scores, ids = index.search(qv, k)
    hits = []
    for score, i in zip(scores[0], ids[0]):
        if i == -1:
            continue
        hits.append((float(score), meta[i]))
    return hits

def build_context(hits):
    blocks = []
    for score, m in hits:
        blocks.append(f"[Source: {m['source']} | chunk: {m['chunk_id']} | score: {score:.3f}]\n{m['text']}")
    return "\n\n---\n\n".join(blocks)

def rag_answer(question: str, k: int = 5, temperature: float = 0.2):
    index, meta = load_index_and_meta()
    if index is None or meta is None:
        return None, []

    hits = retrieve(index, meta, question, k=k)
    context = build_context(hits)

    prompt = f"""
Answer the user's question using ONLY the provided context.
If the context is insufficient, say you don't know.

User question: {question}

Context:
{context}

Return the answer and cite like (source: filename, chunk_id).
""".strip()

    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "You are a RAG assistant that strictly uses provided context."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content, hits

st.set_page_config(page_title="Self RAG POC", layout="wide")
st.title("Self RAG POC — Streamlit (FAISS + OpenAI)")

with st.sidebar:
    st.header("Settings")
    k = st.slider("Top-K chunks", 1, 12, 5)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)
    st.caption("After adding new docs to /data, run `python ingest.py` again.")

index, meta = load_index_and_meta()
if index is None:
    st.error("Index not found. Run `python ingest.py` first.")
    st.stop()

st.success(f"Loaded index ✅ | Total chunks: {len(meta)}")

question = st.text_input("Ask your question")
if st.button("Ask") and question.strip():
    with st.spinner("Retrieving + generating answer..."):
        answer, hits = rag_answer(question.strip(), k=k, temperature=temperature)

    st.subheader("Answer")
    st.write(answer)

    st.subheader("Retrieved chunks (evidence)")
    for score, m in hits:
        with st.expander(f"{m['source']} | chunk {m['chunk_id']} | score {score:.3f}"):
            st.write(m["text"])
