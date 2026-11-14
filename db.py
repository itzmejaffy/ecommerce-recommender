"""SQLite storage: products, users, purchases. Seeds demo data on first run."""
import os
import random
import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shop.db")

# (name, brand, price in INR, description) -- 5 products per category
CATALOG = {
    "Smartphones": [
        ("Nova X5 5G Smartphone", "Nova", 24999, "5G phone with AMOLED display, 50MP camera and fast charging"),
        ("Pixelon P8 Smartphone", "Pixelon", 39999, "flagship phone with AI camera, wireless charging and OLED display"),
        ("Liva Lite 4G Smartphone", "Liva", 9999, "budget phone with large battery and dual camera"),
        ("Nova Fast Charger 65W", "Nova", 1499, "fast charging adapter for phones and laptops, USB-C"),
        ("ShieldGuard Phone Case", "ShieldGuard", 499, "shockproof protective case for smartphones"),
    ],
    "Laptops": [
        ("AeroBook 14 Ultrabook", "Aero", 64999, "lightweight laptop with fast SSD, long battery life and backlit keyboard"),
        ("TitanForge Gaming Laptop", "Titan", 89999, "gaming laptop with dedicated graphics, RGB keyboard and high refresh display"),
        ("Aero Wireless Mouse", "Aero", 899, "ergonomic wireless mouse with bluetooth and USB receiver"),
        ("Aero Laptop Backpack", "Aero", 1799, "water resistant backpack that fits 15 inch laptops"),
        ("Portix USB-C Hub 7-in-1", "Portix", 2199, "USB-C hub with HDMI, USB ports and fast charging for laptops"),
    ],
    "Audio": [
        ("BassPods Wireless Earbuds", "Sonara", 2999, "bluetooth earbuds with noise cancellation and long battery life"),
        ("Sonara Studio Headphones", "Sonara", 7999, "over-ear wireless headphones with active noise cancellation"),
        ("Boomly Bluetooth Speaker", "Boomly", 3499, "portable waterproof bluetooth speaker with deep bass"),
        ("Sonara Soundbar 2.1", "Sonara", 11999, "home theatre soundbar with wireless subwoofer and bluetooth"),
        ("Voxa USB Microphone", "Voxa", 4499, "USB condenser microphone for streaming, podcasts and laptops"),
    ],
    "Fitness": [
        ("FlexFit Yoga Mat", "FlexFit", 999, "non slip yoga mat for workouts and stretching"),
        ("IronGrip Adjustable Dumbbells", "IronGrip", 5999, "adjustable dumbbell set for strength training at home"),
        ("PulseBand Fitness Tracker", "Pulse", 3999, "smart fitness band with heart rate, sleep tracking and bluetooth"),
        ("Hydro Steel Water Bottle", "Hydro", 799, "insulated steel bottle for gym, workouts and travel"),
        ("ProWhey Protein Powder", "Muscle", 2499, "whey protein for muscle recovery after workouts and smoothies"),
    ],
    "Kitchen": [
        ("AirCrisp Air Fryer", "Crisp", 6499, "oil free air fryer for healthy cooking"),
        ("BlendMax Smoothie Blender", "BlendMax", 3299, "high speed blender for smoothies and protein shakes"),
        ("ChefEdge Knife Set", "ChefEdge", 2799, "stainless steel kitchen knife set for cooking"),
        ("BrewBuddy Coffee Maker", "Brew", 4199, "drip coffee maker with programmable timer"),
        ("ChefEdge Nonstick Cookware Set", "ChefEdge", 3999, "nonstick pots and pans set for everyday cooking"),
    ],
    "Books": [
        ("Deep Learning Basics", "Paperleaf", 899, "beginner guide to machine learning and python programming"),
        ("Python for Data Analysis", "Paperleaf", 1099, "data analysis with python, pandas and machine learning"),
        ("Healthy Home Cooking", "Paperleaf", 599, "easy healthy recipes and cooking guide"),
        ("The Mindful Runner", "Paperleaf", 549, "running, fitness training and workout motivation"),
        ("The Design of Everyday Things", "Paperleaf", 699, "classic book on product design and usability"),
    ],
}

# demo customers and the categories they tend to buy from
CUSTOMERS = {
    "Asha": ["Smartphones", "Audio"],
    "Ravi": ["Fitness", "Kitchen"],
    "Meera": ["Books", "Kitchen"],
    "Karthik": ["Laptops", "Audio", "Books"],
    "Divya": ["Fitness", "Audio", "Smartphones"],
    "Guest (no history)": [],
}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init(reset=False):
    if reset and os.path.exists(DB):
        os.remove(DB)
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT, category TEXT,
            brand TEXT, price INTEGER, description TEXT);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, product_id INTEGER, UNIQUE(user_id, product_id));
        """
    )
    if c.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        _seed(c)
    c.commit()
    c.close()


def _seed(c):
    by_cat = {}
    for cat, items in CATALOG.items():
        for name, brand, price, desc in items:
            cur = c.execute(
                "INSERT INTO products(name,category,brand,price,description) VALUES(?,?,?,?,?)",
                (name, cat, brand, price, desc),
            )
            by_cat.setdefault(cat, []).append(cur.lastrowid)
    rng = random.Random(7)  # deterministic demo data
    all_ids = [i for ids in by_cat.values() for i in ids]
    for name, cats in CUSTOMERS.items():
        uid = c.execute("INSERT INTO users(name) VALUES(?)", (name,)).lastrowid
        if not cats:
            continue
        pool = [i for cat in cats for i in by_cat[cat]]
        picks = rng.sample(pool, min(6, len(pool)))
        picks.insert(0, rng.choice([i for i in all_ids if i not in picks]))  # one older, off-taste purchase
        for pid in picks:
            c.execute("INSERT OR IGNORE INTO purchases(user_id,product_id) VALUES(?,?)", (uid, pid))


def products():
    c = conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM products ORDER BY id")]
    c.close()
    return rows


def users():
    c = conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM users ORDER BY id")]
    c.close()
    return rows


def purchase_pairs():
    """All (user_id, product_id) pairs, oldest first."""
    c = conn()
    rows = [(r["user_id"], r["product_id"]) for r in c.execute("SELECT user_id, product_id FROM purchases ORDER BY id")]
    c.close()
    return rows


def add_purchase(user_id, product_id):
    c = conn()
    cur = c.execute("INSERT OR IGNORE INTO purchases(user_id,product_id) VALUES(?,?)", (user_id, product_id))
    c.commit()
    added = cur.rowcount > 0
    c.close()
    return added
