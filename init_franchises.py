from app import app, db
from models import Franchise
from werkzeug.security import generate_password_hash

def init_franchises():
    with app.app_context():
        # Predefined franchises with their secret passwords
        franchises = [
            {"name": "Downtown Motors", "location": "Hyderabad", "password": "downtown@2024"},
            {"name": "City Auto Hub", "location": "Secunderabad", "password": "cityhub@2024"},
            {"name": "Mumbai West Auto", "location": "Mumbai", "password": "mumbai@2024"},
            {"name": "Delhi South Dealers", "location": "Delhi", "password": "delhi@2024"},
            {"name": "Bangalore Tech Drive", "location": "Bangalore", "password": "bangalore@2024"}
        ]
        
        for f_data in franchises:
            existing = Franchise.query.filter_by(name=f_data["name"]).first()
            if not existing:
                # Create new franchise
                franchise = Franchise(
                    name=f_data["name"],
                    location=f_data["location"],
                    franchise_password=generate_password_hash(f_data["password"])
                )
                db.session.add(franchise)
                print(f"✅ Added franchise: {f_data['name']}")
            else:
                # Update existing franchise password
                existing.franchise_password = generate_password_hash(f_data["password"])
                print(f"🔄 Updated password for franchise: {f_data['name']}")
        
        db.session.commit()
        print("✅ All franchises initialized!")

if __name__ == "__main__":
    init_franchises()