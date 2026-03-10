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

    def _keyword_score(self, query: str, description: str) -> float:
        """
        Calculate a keyword-based match score.
        Looks for important keywords in the description.
        """
        query_lower = query.lower()
        desc_lower = description.lower()
        
        # Define interest keywords and corresponding course indicators
        interest_keywords = {
            "ai": ["artificial intelligence", "ai", "intelligent systems", "automation"],
            "machine learning": ["machine learning", "deep learning", "ml models"],
            "coding": ["programming", "coding", "algorithms", "software engineering", "applications"],
            "data": ["data", "statistics", "data analysis", "big data", "patterns"],
            "cyber": ["security", "cryptography", "hacking", "vulnerabilities", "forensics"],
            "electronics": ["electronics", "circuits", "embedded", "hardware", "devices"],
            "communication": ["communication", "signal processing", "telecom", "networks"],
            "power": ["power", "electrical", "generation", "transmission", "machines"],
            "machines": ["machines", "mechanical", "design", "thermodynamics", "manufacturing"],
            "physics": ["physics", "mechanics", "engineering", "design"],
            "structures": ["structural", "concrete", "steel", "buildings", "infrastructure"],
            "civil": ["civil", "construction", "surveying", "infrastructure", "buildings"],
        }
        
        score = 0
        matched_keywords = 0
        
        for topic, keywords in interest_keywords.items():
            if any(kw in query_lower for kw in keywords):
                for kw in keywords:
                    if kw in desc_lower:
                        score += 1
                        matched_keywords += 1
        
        # Normalize score
        if matched_keywords > 0:
            score = min(1.0, score / (matched_keywords * 0.5))
        
        return score

    def recommend(self, interest_text: str, top_k: int = 3) -> List[Dict]:
        # Check if the query is about sports or general non-academic interests
        sports_keywords = [
            "cricket", "football", "basketball", "tennis", "badminton", "volleyball", 
            "hockey", "baseball", "soccer", "swimming", "running", "athletics", 
            "sports", "game", "play", "watching", "fan", "team", "player", "match",
            "tournament", "league", "stadium", "field", "court", "gym", "exercise",
            "fitness", "workout", "dance", "music", "singing", "art", "painting",
            "drawing", "acting", "drama", "theatre", "movie", "film", "cinema",
            "travel", "tourism", "roaming", "adventure", "explore", "vacation", "trip",
            "cooking", "food", "reading", "books", "novels", "gaming", "video games",
            "social media", "internet", "shopping", "fashion", "photography", "nature",
            "animals", "pets", "gardening", "crafts", "hiking", "camping", "beach",
            "mountains", "forest", "ocean", "sky", "stars", "sleeping", "resting"
        ]
        
        # Check for negative interest indicators
        negative_indicators = [
            "nothing", "no interest", "don't like", "hate", "dislike", "not interested",
            "bored", "boring", "tired", "exhausted", "lazy", "no hobbies", "no passion",
            "indifferent", "apathetic", "neutral", "meh", "whatever", "don't care"
        ]
        
        interest_lower = interest_text.lower()
        is_sports_or_general = any(keyword in interest_lower for keyword in sports_keywords)
        has_negative_indicator = any(neg in interest_lower for neg in negative_indicators)
        
        # If it's clearly a sports/general interest or has negative indicators, don't recommend academic courses
        if (is_sports_or_general or has_negative_indicator) and not any(academic_kw in interest_lower for academic_kw in [
            "coding", "programming", "ai", "machine learning", "data", "cyber", "security",
            "electronics", "communication", "power", "electrical", "mechanical", "civil",
            "engineering", "physics", "math", "chemistry", "computer", "software", "hardware",
            "algorithm", "database", "network", "web", "mobile", "app", "design", "analysis",
            "science", "technology", "research", "development", "automation", "robotics"
        ]):
            return []  # Return empty list to trigger the "couldn't match" message
        
        # Use TF-IDF similarity
        user_vec = self.vectorizer.transform([interest_text])
        tfidf_sims = cosine_similarity(user_vec, self.course_matrix)[0]
        
        # Calculate keyword-based scores
        keyword_scores = np.array([
            self._keyword_score(interest_text, c["description"]) 
            for c in self.courses
        ])
        
        # Combine both scores (weighted)
        combined_scores = 0.6 * tfidf_sims + 0.4 * keyword_scores
        
        idx = np.argsort(combined_scores)[::-1][:top_k]

        results = []
        for i in idx:
            c = self.courses[i]
            score = float(combined_scores[i])
            # Only include results above a minimum threshold, but be lenient
            if score > 0.05 or keyword_scores[i] > 0.1:
                results.append(
                    {
                        "code": c["code"],
                        "name": c["name"],
                        "description": c["description"],
                        "score": score,
                    }
                )
        
        return results
