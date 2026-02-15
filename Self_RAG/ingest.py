import os, json
import numpy as np
import faiss
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DATA_DIR = "data"
INDEX_DIR = "index"
os.makedirs(INDEX_DIR, exist_ok=True)

EMBED_MODEL = "text-embedding-3-small"

def read_all_files():
    texts = []
    for fn in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, fn)
        if os.path.isfile(path) and fn.lower().endswith((".txt", ".md")):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                texts.append((fn, f.read()))
    return texts

def chunk_text(text, chunk_size=800, overlap=150):
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+chunk_size])
        i += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]

def embed_texts(text_list):
    resp = client.embeddings.create(model=EMBED_MODEL, input=text_list)
    vectors = np.array([d.embedding for d in resp.data], dtype="float32")
    return vectors

def main():
    docs = read_all_files()
    if not docs:
        raise SystemExit("No .txt/.md files found in data/")

    all_chunks = []
    meta = []

    for fn, content in docs:
        chunks = chunk_text(content)
        for idx, ch in enumerate(chunks):
            all_chunks.append(ch)
            meta.append({"source": fn, "chunk_id": idx, "text": ch})

    print(f"Total chunks: {len(all_chunks)}")

    vectors = embed_texts(all_chunks)
    dim = vectors.shape[1]

    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(vectors)
    index.add(vectors)

    faiss.write_index(index, os.path.join(INDEX_DIR, "docs.faiss"))
    with open(os.path.join(INDEX_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("✅ Saved: index/docs.faiss and index/meta.json")

if __name__ == "__main__":
    main()
