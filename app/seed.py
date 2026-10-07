from app.database import SessionLocal
from app.models import Product

SAMPLE_PRODUCTS = [
    ("Classic Sneakers", "Comfortable everyday white sneakers.", 4500,
     "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=600"),
    ("Canvas Backpack", "Roomy backpack for school or travel.", 3200,
     "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=600"),
    ("Wireless Headphones", "Over-ear, 30 hour battery.", 8900,
     "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600"),
    ("Steel Water Bottle", "Keeps drinks cold for 24 hours.", 1800,
     "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=600"),
    ("Desk Lamp", "Warm LED lamp with dimmer.", 2700,
     "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?w=600"),
    ("Notebook Set", "Three dotted notebooks.", 1200,
     "https://images.unsplash.com/photo-1531346878377-a5be20888e57?w=600"),
]


def seed_products():
    db = SessionLocal()
    try:
        if db.query(Product).count() == 0:
            for name, desc, price, img in SAMPLE_PRODUCTS:
                db.add(Product(name=name, description=desc, price_cents=price, image_url=img))
            db.commit()
    finally:
        db.close()
