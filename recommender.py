"""Hybrid product recommender.

content score : TF-IDF cosine similarity between a product and the customer's past purchases
collab score  : item-item co-purchase similarity (customers who bought A also bought B)
final score   : alpha * content + (1 - alpha) * collab, with recent purchases weighted higher.
Customers with no history get popularity-based suggestions (cold start).
"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _norm(v):
    m = v.max() if len(v) else 0
    return v / m if m > 0 else v


class Recommender:
    def __init__(self, products, purchases, alpha=0.6, half_life=5):
        self.products = products
        self.ids = [p["id"] for p in products]
        self.idx = {pid: i for i, pid in enumerate(self.ids)}
        self.alpha, self.half_life = alpha, half_life

        # --- content model
        docs = [f'{p["name"]} {p["category"]} {p["category"]} {p["brand"]} {p["description"]}' for p in products]
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.tfidf = self.vec.fit_transform(docs)
        self.content_sim = cosine_similarity(self.tfidf)
        self.title_text = [f'{p["name"]} {p["category"]} {p["brand"]}'.lower() for p in products]
        self.desc_text = [p["description"].lower() for p in products]

        # --- collaborative model
        self.history = {}  # user_id -> [product_id, ...] oldest first
        for u, p in purchases:
            self.history.setdefault(u, []).append(p)
        users = list(self.history)
        m = np.zeros((len(users), len(products)))
        for r, u in enumerate(users):
            for p in self.history[u]:
                m[r, self.idx[p]] = 1
        co = m.T @ m
        d = np.sqrt(np.diag(co))
        d[d == 0] = 1
        self.collab_sim = co / np.outer(d, d)
        np.fill_diagonal(self.collab_sim, 0)
        self.popularity = _norm(m.sum(axis=0))

    # ---------- scoring helpers
    def _affinity(self, hist):
        """How well each product fits a purchase history (0..1)."""
        rows = [self.idx[h] for h in hist]
        n = len(rows)
        w = np.array([0.5 ** ((n - 1 - i) / self.half_life) for i in range(n)])
        w /= w.sum()
        content = _norm(w @ self.content_sim[rows])
        collab = _norm(w @ self.collab_sim[rows])
        return self.alpha * content + (1 - self.alpha) * collab

    def _relevance(self, query):
        """How well each product matches a search query (0..1)."""
        cos = cosine_similarity(self.vec.transform([query]), self.tfidf).ravel()
        tokens = query.lower().split()
        # substring match handles partial words ("laptop" vs "laptops"); title hits count double a description hit
        sub = np.zeros(len(self.ids))
        for i, (title, desc) in enumerate(zip(self.title_text, self.desc_text)):
            hits = [1.0 if t in title else 0.5 if t in desc else 0.0 for t in tokens]
            sub[i] = 0.8 * np.mean(hits) if hits else 0.0
        return np.maximum(cos, sub)

    def _reason(self, hist, j):
        rows = [self.idx[h] for h in hist]
        s = self.alpha * self.content_sim[rows, j] + (1 - self.alpha) * self.collab_sim[rows, j]
        return "Because you bought " + self.products[rows[int(np.argmax(s))]]["name"]

    def _pack(self, i, score, reason=""):
        p = dict(self.products[i])
        p["score"], p["reason"] = round(float(score), 3), reason
        return p

    # ---------- public API
    def recommend(self, user_id, k=6, exclude=(), query=None):
        """Suggestions from purchase history. `query` nudges them toward what the customer is browsing."""
        hist = self.history.get(user_id, [])
        score = self._affinity(hist) if hist else self.popularity.copy()
        if query:
            score = score + 0.3 * _norm(self._relevance(query))
        skip = set(hist) | set(exclude)
        out = []
        for i in np.argsort(-score):
            if self.ids[i] in skip:
                continue
            reason = self._reason(hist, i) if hist else "Popular with other customers"
            out.append(self._pack(i, score[i], reason))
            if len(out) == k:
                break
        return out

    def search(self, user_id, query, k=8):
        """Keyword search, re-ranked so items matching the customer's taste rise."""
        query = (query or "").strip()
        if not query:  # nothing typed: show trending items
            return [self._pack(i, self.popularity[i]) for i in np.argsort(-self.popularity)[:k]]
        rel = self._relevance(query)
        hist = self.history.get(user_id, [])
        aff = self._affinity(hist) if hist else np.zeros(len(self.ids))
        score = 0.7 * rel + 0.3 * aff
        return [self._pack(i, score[i]) for i in np.argsort(-score) if rel[i] > 0.05][:k]
