"""Flask app: storefront page + JSON API.  Run with:  python app.py"""
import threading

from flask import Flask, jsonify, render_template, request

import db
from recommender import Recommender

app = Flask(__name__)
db.init()

_lock = threading.Lock()
_state = {}


def rebuild():
    """(Re)train the model from the database. Called at start and after every purchase."""
    with _lock:
        _state["rec"] = Recommender(db.products(), db.purchase_pairs())


rebuild()


def _mark_bought(items, user_id):
    bought = set(_state["rec"].history.get(user_id, []))
    for p in items:
        p["bought"] = p["id"] in bought
    return items


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/users")
def users():
    return jsonify(db.users())


@app.get("/api/search")
def search():
    user_id = request.args.get("user_id", type=int)
    q = request.args.get("q", "")
    rec = _state["rec"]
    results = _mark_bought(rec.search(user_id, q), user_id)
    shown = [p["id"] for p in results]
    # the key feature: every search also returns suggestions based on purchase history
    suggestions = _mark_bought(rec.recommend(user_id, k=5, exclude=shown, query=q or None), user_id)
    return jsonify({"query": q, "results": results, "suggestions": suggestions})


@app.get("/api/history")
def history():
    user_id = request.args.get("user_id", type=int)
    rec = _state["rec"]
    by_id = {p["id"]: p for p in rec.products}
    return jsonify([by_id[pid] for pid in reversed(rec.history.get(user_id, []))])


@app.post("/api/purchase")
def purchase():
    data = request.get_json(force=True)
    added = db.add_purchase(int(data["user_id"]), int(data["product_id"]))
    if added:
        rebuild()
    return jsonify({"ok": True, "added": added})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
