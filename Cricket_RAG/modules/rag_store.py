from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

class PlayerRAGStore:
    def __init__(self, store_dir: Path):
        self.store_dir = store_dir
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.store_dir / "players.faiss"
        self.meta_path = self.store_dir / "players_meta.json"

        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = None
        self.meta: List[Dict[str, Any]] = []

        if self.index_path.exists() and self.meta_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))

    def _player_to_text(self, p: Dict[str, Any]) -> str:
        return f"Player: {p['name']}\nRole: {p['role']}\nRating: {p['rating']}"

    def build(self, players: List[Dict[str, Any]]) -> None:
        texts = [self._player_to_text(p) for p in players]
        emb = self.model.encode(texts, normalize_embeddings=True)
        emb = np.array(emb, dtype="float32")

        dim = emb.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(emb)

        self.meta = players
        faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")

    def search(self, query: str, k: int = 50) -> List[Dict[str, Any]]:
        if self.index is None:
            return []
        q = self.model.encode([query], normalize_embeddings=True)
        q = np.array(q, dtype="float32")
        scores, ids = self.index.search(q, min(k, len(self.meta)))
        results = []
        for idx, score in zip(ids[0].tolist(), scores[0].tolist()):
            if idx < 0:
                continue
            item = dict(self.meta[idx])
            item["_score"] = float(score)
            results.append(item)
        return results
