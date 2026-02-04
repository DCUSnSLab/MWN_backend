from app import app, db
from models import MarketReport

with app.app_context():
    # This will create any tables that don't exist yet (MarketReport)
    db.create_all()
    print("✅ Created all tables (including MarketReport if missing).")
