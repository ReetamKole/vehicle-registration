from werkzeug.security import generate_password_hash, check_password_hash

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Franchise(db.Model):
    __tablename__ = "franchises"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(200), nullable=True)

    vehicles = db.relationship("Vehicle", backref="franchise", lazy=True)
    owners = db.relationship("FranchiseOwner", backref="franchise", lazy=True)


class FranchiseOwner(db.Model):
    __tablename__ = "franchise_owners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # will store HASH here
    franchise_id = db.Column(db.Integer, db.ForeignKey("franchises.id"), nullable=False)

    # ---------- hashing ----------
    def set_password(self, raw_password: str):
        # store the HASH in the password column
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        # compare raw_password with the HASH in self.password
        return check_password_hash(self.password, raw_password)


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    vehicles = db.relationship("Vehicle", backref="owner", lazy=True)


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    registration_number = db.Column(db.String(50), unique=True, nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    issue_date = db.Column(db.Date, nullable=False)

    franchise_id = db.Column(db.Integer, db.ForeignKey("franchises.id"), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
