import json
import os
import pickle
from typing import List, Dict

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EMB_PATH = os.path.join(DATA_DIR, "kb_embeddings.pkl")


class EllenkiRetrievalService:
    def __init__(self):
        # small, fast embedding model
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.documents: List[str] = []
        self.metadata: List[Dict] = []
        self.embeddings = None
        self._load_or_build_index()

    def _load_or_build_index(self):
        # load if already built
        if os.path.exists(EMB_PATH):
            with open(EMB_PATH, "rb") as f:
                data = pickle.load(f)
            self.documents = data["documents"]
            self.metadata = data["metadata"]
            self.embeddings = data["embeddings"]
            return

        faq_path = os.path.join(DATA_DIR, "ellenki_faq.json")
        docs_path = os.path.join(DATA_DIR, "ellenki_docs.txt")

        # Add FAQ as short docs
        if os.path.exists(faq_path):
            with open(faq_path, "r", encoding="utf-8") as f:
                faq_items = json.load(f)
            for item in faq_items:
                text = f"Q: {item['question']}\nA: {item['answer']}"
                self.documents.append(text)
                self.metadata.append({"type": "faq"})

        # Add longer docs by paragraph
        if os.path.exists(docs_path):
            with open(docs_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            for para in full_text.split("\n\n"):
                para = para.strip()
                if len(para) > 40:
                    self.documents.append(para)
                    self.metadata.append({"type": "doc"})

        # Compute embeddings
        self.embeddings = self.model.encode(self.documents, show_progress_bar=True)

        # Save to disk
        with open(EMB_PATH, "wb") as f:
            pickle.dump(
                {
                    "documents": self.documents,
                    "metadata": self.metadata,
                    "embeddings": self.embeddings,
                },
                f,
            )

    def retrieve(self, query: str, top_k: int = 5) -> List[str]:
        if not self.documents:
            return []

        q_emb = self.model.encode([query])
        sims = cosine_similarity(q_emb, self.embeddings)[0]
        top_idx = np.argsort(sims)[::-1][:top_k]

        return [self.documents[i] for i in top_idx]
