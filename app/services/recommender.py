import json
import os
from typing import List, Dict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class CourseRecommender:
    def __init__(self):
        courses_path = os.path.join(DATA_DIR, "courses.json")
        with open(courses_path, "r", encoding="utf-8") as f:
            self.courses: List[Dict] = json.load(f)

        corpus = [c["description"] for c in self.courses]
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.course_matrix = self.vectorizer.fit_transform(corpus)

    def recommend(self, interest_text: str, top_k: int = 3) -> List[Dict]:
        user_vec = self.vectorizer.transform([interest_text])
        sims = cosine_similarity(user_vec, self.course_matrix)[0]
        idx = np.argsort(sims)[::-1][:top_k]

        results = []
        for i in idx:
            c = self.courses[i]
            results.append(
                {
                    "code": c["code"],
                    "name": c["name"],
                    "description": c["description"],
                    "score": float(sims[i]),
                }
            )
        return results
