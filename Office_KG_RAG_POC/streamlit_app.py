import os, json, re
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in .env")
if not NEO4J_URI or not NEO4J_URI.startswith("neo4j"):
    raise SystemExit("Missing/invalid NEO4J_URI in .env (Aura uses neo4j+s://...)")
if not NEO4J_PASSWORD:
    raise SystemExit("Missing NEO4J_PASSWORD in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

INDEX_DIR = "index"
FAISS_PATH = os.path.join(INDEX_DIR, "docs.faiss")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

ROLES = ["EMPLOYEE", "MANAGER", "HR", "ADMIN"]

@st.cache_resource(show_spinner=False)
def load_faiss_and_meta():
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

def retrieve_vectors(index, meta: List[Dict[str, Any]], q: str, role: str, k: int):
    qv = embed_query(q)
    over = min(max(k * 6, 12), 60)
    scores, ids = index.search(qv, over)

    hits = []
    for score, i in zip(scores[0], ids[0]):
        if i == -1:
            continue
        m = meta[i]
        if role in m.get("allowed_roles", []):
            hits.append((float(score), m))
        if len(hits) >= k:
            break
    return hits

@st.cache_resource(show_spinner=False)
def get_driver():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    return driver

def extract_terms(question: str) -> List[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", question)
    seen, out = set(), []
    for t in terms:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
        if len(out) >= 8:
            break
    return out

def kg_search(driver, question: str, role: str, limit: int = 10) -> List[Dict[str, Any]]:
    terms = extract_terms(question)
    cypher = """
    MATCH (s:Entity)-[r]->(o:Entity)
    WHERE any(t IN $terms WHERE toLower(s.name) CONTAINS toLower(t) OR toLower(o.name) CONTAINS toLower(t))
      AND $role IN s.allowed_roles
      AND $role IN o.allowed_roles
      AND $role IN r.allowed_roles
    RETURN s.name AS subject, type(r) AS predicate, o.name AS object, r.source AS source
    LIMIT $limit
    """
    with driver.session() as session:
        return session.run(cypher, terms=terms, role=role, limit=limit).data()

def build_context(vec_hits, kg_facts):
    parts = []
    if kg_facts:
        lines = [f"- ({f['subject']}) -[{f['predicate']}]-> ({f['object']}) [source: {f.get('source','')}]" for f in kg_facts]
        parts.append("Knowledge Graph Facts:\n" + "\n".join(lines))

    if vec_hits:
        blocks = []
        for score, m in vec_hits:
            blocks.append(f"[Vector Source: {m['source']} | chunk: {m['chunk_id']} | score: {score:.3f}]\n{m['text']}")
        parts.append("Vector Evidence:\n" + "\n\n---\n\n".join(blocks))

    return "\n\n".join(parts).strip()

def ask_llm(question: str, role: str, context: str, temperature: float):
    prompt = f"""
You are an office-management assistant with strict role-based access control.

Role: {role}

Answer using ONLY the context below.
If context is insufficient OR the information is not available to this role, reply:
"Not available for your role or not found in provided documents."

User question: {question}

Context:
{context}

Citations:
- Vector: (source: filename, chunk_id)
- KG: (kg: subject-predicate-object, source)
""".strip()

    resp = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "Use only context. Never reveal restricted info."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content

# -------------------- UI --------------------
st.set_page_config(page_title="Office KG+RAG (Neo4j Aura)", layout="wide")
st.title("Office Management Chatbot — Hybrid KG + RAG (Neo4j Aura + FAISS)")

with st.sidebar:
    role = st.selectbox("Role", ROLES, index=0)
    k = st.slider("Top-K vector chunks", 1, 12, 5)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.2, 0.05)

index, meta = load_faiss_and_meta()
if index is None:
    st.error("Vector index not found. Run `python ingest.py` first.")
    st.stop()

try:
    driver = get_driver()
except Exception as e:
    st.error(f"Aura connection failed: {e}")
    st.stop()

st.success(f"Loaded ✅ | chunks: {len(meta)} | Neo4j: {NEO4J_URI}")

q = st.text_input("Ask a question", placeholder="e.g., Who can book Board Room? What is ACME internet SLA?")
if st.button("Ask") and q.strip():
    with st.spinner("Retrieving from KG + vectors..."):
        vec_hits = retrieve_vectors(index, meta, q.strip(), role, k)
        kg_facts = kg_search(driver, q.strip(), role, limit=10)
        context = build_context(vec_hits, kg_facts)
        ans = ask_llm(q.strip(), role, context, temperature)

    st.subheader("Answer")
    st.write(ans)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("KG Evidence")
        st.write(kg_facts if kg_facts else "No KG facts for your role.")
    with col2:
        st.subheader("Vector Evidence")
        if not vec_hits:
            st.write("No vector chunks for your role.")
        else:
            for score, m in vec_hits:
                with st.expander(f"{m['source']} | chunk {m['chunk_id']} | score {score:.3f}"):
                    st.write(m["text"])
