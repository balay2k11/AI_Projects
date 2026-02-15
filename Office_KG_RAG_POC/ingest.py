import os, json, re, hashlib, traceback
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss
from dotenv import load_dotenv
from openai import OpenAI
from neo4j import GraphDatabase

# -------------------- Load ENV early --------------------
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEO4J_URI = os.getenv("NEO4J_URI")          # Aura: neo4j+s://...
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in .env")
if not NEO4J_URI or not NEO4J_URI.startswith("neo4j"):
    raise SystemExit("Missing/invalid NEO4J_URI in .env (Aura uses neo4j+s://...)")
if not NEO4J_PASSWORD:
    raise SystemExit("Missing NEO4J_PASSWORD in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

DATA_DIR = "data"
INDEX_DIR = "index"
os.makedirs(INDEX_DIR, exist_ok=True)

FAISS_PATH = os.path.join(INDEX_DIR, "docs.faiss")
META_PATH = os.path.join(INDEX_DIR, "meta.json")

EMBED_MODEL = "text-embedding-3-small"
KG_EXTRACT_MODEL = "gpt-4o-mini"

# -------------------- RBAC --------------------
FILE_ROLE_MAP = {
    "vendor_contract_acme_internet.txt": ["ADMIN"],
    "hr_leave_policy.txt": ["HR", "MANAGER"],
}
ALL_ROLES = ["EMPLOYEE", "MANAGER", "HR", "ADMIN"]

def allowed_roles_for_file(filename: str) -> List[str]:
    return FILE_ROLE_MAP.get(filename, ALL_ROLES)

def guess_domain(filename: str) -> str:
    fn = filename.lower()
    if "hr" in fn or "leave" in fn:
        return "HR"
    if "vendor" in fn or "contract" in fn or "internet" in fn:
        return "IT"
    if "room" in fn or "meeting" in fn:
        return "Facilities"
    return "General"

# -------------------- Docs --------------------
def read_all_files() -> List[Tuple[str, str]]:
    if not os.path.isdir(DATA_DIR):
        raise SystemExit(f"Missing folder: {DATA_DIR}")

    docs = []
    for fn in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, fn)
        if os.path.isfile(path) and fn.lower().endswith((".txt", ".md")):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if content:
                    docs.append((fn, content))
    return docs

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 160) -> List[str]:
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + chunk_size])
        i += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]

# -------------------- Embeddings --------------------
def embed_texts(text_list: List[str]) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=text_list)
    vectors = np.array([d.embedding for d in resp.data], dtype="float32")
    return vectors

# -------------------- Neo4j Aura --------------------
def get_driver():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # After-fix: verify connection early
    driver.verify_connectivity()
    return driver

def init_constraints(driver):
    stmts = [
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Doc) REQUIRE d.id IS UNIQUE",
    ]
    with driver.session() as session:
        for s in stmts:
            session.run(s)

def clear_graph(driver):
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")

def upsert_doc(tx, doc_id: str, source: str, domain: str, allowed_roles: List[str]):
    tx.run(
        """
        MERGE (d:Doc {id: $doc_id})
        SET d.source = $source,
            d.domain = $domain,
            d.allowed_roles = $allowed_roles
        """,
        doc_id=doc_id, source=source, domain=domain, allowed_roles=allowed_roles
    )

def upsert_entity(tx, ent_id: str, name: str, etype: str, domain: str, allowed_roles: List[str]):
    tx.run(
        """
        MERGE (e:Entity {id: $id})
        SET e.name = $name,
            e.type = $type,
            e.domain = $domain,
            e.allowed_roles = $allowed_roles
        """,
        id=ent_id, name=name, type=etype, domain=domain, allowed_roles=allowed_roles
    )

def upsert_relation(tx, subj_id: str, predicate: str, obj_id: str, allowed_roles: List[str], source: str):
    rel = re.sub(r"[^A-Z0-9_]", "_", predicate.upper())
    tx.run(
        f"""
        MATCH (s:Entity {{id: $sid}}), (o:Entity {{id: $oid}})
        MERGE (s)-[r:{rel}]->(o)
        SET r.allowed_roles = $allowed_roles,
            r.source = $source
        """,
        sid=subj_id, oid=obj_id, allowed_roles=allowed_roles, source=source
    )

def link_doc_mentions(tx, doc_id: str, ent_id: str):
    tx.run(
        """
        MATCH (d:Doc {id: $doc_id}), (e:Entity {id: $eid})
        MERGE (d)-[:MENTIONS]->(e)
        """,
        doc_id=doc_id, eid=ent_id
    )

# -------------------- KG Extraction --------------------
def stable_entity_id(etype: str, name: str) -> str:
    raw = f"{etype}:{name}".strip().lower()
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())[:32].strip("_")
    return f"{etype}:{safe}:{h}"

def extract_triples_llm(text: str) -> List[Dict[str, Any]]:
    prompt = f"""
Return ONLY a valid JSON array of triples. No markdown. No extra text.

Format:
[
  {{
    "subject": {{"name":"...","type":"Room|Vendor|Policy|Procedure|SLA|Department|Role|Asset|Service"}},
    "predicate": "BOOKABLE_BY|HAS_SLA|APPLIES_TO|APPROVED_BY|OWNS|RELATED_TO|REQUIRES|SUPPORTS",
    "object": {{"name":"...","type":"Room|Vendor|Policy|Procedure|SLA|Department|Role|Asset|Service"}}
  }}
]

If nothing, return [].

Text:
{text}
""".strip()

    resp = client.chat.completions.create(
        model=KG_EXTRACT_MODEL,
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )

    raw = resp.choices[0].message.content.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [t for t in data if isinstance(t, dict) and "subject" in t and "predicate" in t and "object" in t]
        return []
    except Exception:
        return []

# -------------------- MAIN --------------------
def main():
    print("DEBUG CWD:", os.getcwd())
    print("DEBUG DATA_DIR abs:", os.path.abspath(DATA_DIR))
    print("DEBUG INDEX_DIR abs:", os.path.abspath(INDEX_DIR))

    docs = read_all_files()
    if not docs:
        raise SystemExit("No .txt/.md files found in data/ (or files are empty)")

    # 1) Build chunks + metadata
    all_chunks: List[str] = []
    meta: List[Dict[str, Any]] = []

    for fn, content in docs:
        domain = guess_domain(fn)
        roles = allowed_roles_for_file(fn)
        chunks = chunk_text(content)

        for i, ch in enumerate(chunks):
            all_chunks.append(ch)
            meta.append({
                "source": fn,
                "chunk_id": i,
                "domain": domain,
                "allowed_roles": roles,
                "text": ch
            })

    print("DEBUG docs:", [d[0] for d in docs])
    print("DEBUG total chunks:", len(all_chunks))

    # 2) Build FAISS FIRST (so even if Neo4j fails, index is saved)
    vectors = embed_texts(all_chunks)
    faiss.normalize_L2(vectors)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    print("DEBUG saving FAISS to:", os.path.abspath(FAISS_PATH))
    print("DEBUG saving META  to:", os.path.abspath(META_PATH))

    faiss.write_index(index, FAISS_PATH)
    print("✅ FAISS saved OK")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("✅ META saved OK")

    # 3) Now build KG in Aura
    driver = get_driver()
    try:
        init_constraints(driver)
        clear_graph(driver)
        init_constraints(driver)

        with driver.session() as session:
            for fn, content in docs:
                domain = guess_domain(fn)
                roles = allowed_roles_for_file(fn)
                doc_id = os.path.splitext(fn)[0]

                session.execute_write(upsert_doc, doc_id, fn, domain, roles)

                triples = extract_triples_llm(content)
                print(f"DEBUG {fn}: triples =", len(triples))

                for t in triples:
                    pred = (t.get("predicate") or "").strip()
                    subj = t.get("subject") or {}
                    obj = t.get("object") or {}

                    s_name = (subj.get("name") or "").strip()
                    s_type = (subj.get("type") or "Entity").strip()
                    o_name = (obj.get("name") or "").strip()
                    o_type = (obj.get("type") or "Entity").strip()

                    if not pred or not s_name or not o_name:
                        continue

                    sid = stable_entity_id(s_type, s_name)
                    oid = stable_entity_id(o_type, o_name)

                    session.execute_write(upsert_entity, sid, s_name, s_type, domain, roles)
                    session.execute_write(upsert_entity, oid, o_name, o_type, domain, roles)
                    session.execute_write(upsert_relation, sid, pred, oid, roles, fn)

                    session.execute_write(link_doc_mentions, doc_id, sid)
                    session.execute_write(link_doc_mentions, doc_id, oid)

        print("✅ Knowledge graph built in Neo4j Aura.")
    finally:
        driver.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n❌ INGEST FAILED:", repr(e))
        traceback.print_exc()
        raise
