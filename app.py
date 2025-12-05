import os
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from models import db, Franchise, FranchiseOwner, Customer, Vehicle

app = Flask(__name__)

# --- DB config ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

db.init_app(app)


def create_tables_and_seed():
    db.create_all()

    if not Franchise.query.first():
        f1 = Franchise(name="Downtown Motors", location="Hyderabad")
        f2 = Franchise(name="City Auto Hub", location="Secunderabad")
        db.session.add_all([f1, f2])
        db.session.commit()

        owner1 = FranchiseOwner(
            name="Ravi Kumar",
            email="ravi@franchise.com",
            franchise_id=f1.id,
        )
        owner1.set_password("password123")
        owner2 = FranchiseOwner(
            name="Anita Sharma",
            email="anita@franchise.com",
            franchise_id=f2.id,
        )
        owner2.set_password("password123")
        db.session.add_all([owner1, owner2])
        db.session.commit()

with app.app_context():
    create_tables_and_seed()


@app.route("/")
def index():
    return render_template("index.html")


# ---------- Vehicle Registration (Create) ----------
@app.route("/register", methods=["GET", "POST"])
def register_vehicle():
    franchises = Franchise.query.all()
    if request.method == "POST":
        # Customer details
        customer_name = request.form.get("customer_name")
        customer_email = request.form.get("customer_email")
        customer_phone = request.form.get("customer_phone")

        # Vehicle details
        reg_no = request.form.get("registration_number")
        brand = request.form.get("brand")
        model = request.form.get("model")
        issue_date_str = request.form.get("issue_date")
        franchise_id = request.form.get("franchise_id")

        if not (
            customer_name
            and customer_email
            and customer_phone
            and reg_no
            and brand
            and model
            and issue_date_str
            and franchise_id
        ):
            flash("All fields are required", "danger")
            return redirect(url_for("register_vehicle"))

        try:
            issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid issue date format", "danger")
            return redirect(url_for("register_vehicle"))

        # Find or create customer
        customer = Customer.query.filter_by(
            email=customer_email, phone=customer_phone
        ).first()
        if not customer:
            customer = Customer(
                name=customer_name,
                email=customer_email,
                phone=customer_phone,
            )
            db.session.add(customer)
            db.session.commit()

        vehicle = Vehicle(
            registration_number=reg_no,
            brand=brand,
            model=model,
            issue_date=issue_date,
            franchise_id=int(franchise_id),
            owner_id=customer.id,
        )
        db.session.add(vehicle)
        db.session.commit()

        flash("Vehicle registered successfully!", "success")
        return redirect(url_for("index"))

    return render_template("register_vehicle.html", franchises=franchises)


# ---------- Franchise Owner Login + Dashboard ----------
@app.route("/franchise/login", methods=["GET", "POST"])
def franchise_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        owner = FranchiseOwner.query.filter_by(email=email).first()

        if owner and owner.check_password(password):
            session["owner_id"] = owner.id
            session["franchise_id"] = owner.franchise_id
            flash("Logged in successfully", "success")
            return redirect(url_for("franchise_dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("franchise_login"))

    return render_template("franchise_login.html")

@app.route("/franchise/signup", methods=["GET", "POST"])
def franchise_signup():
    if request.method == "POST":
        owner_name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        franchise_name = request.form.get("franchise_name")
        franchise_location = request.form.get("franchise_location")

        # Basic validation
        if not all([owner_name, email, password, confirm_password, franchise_name]):
            flash("All fields except location are required", "danger")
            return redirect(url_for("franchise_signup"))

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("franchise_signup"))

        # Check if email already exists
        existing_owner = FranchiseOwner.query.filter_by(email=email).first()
        if existing_owner:
            flash("An account with this email already exists", "warning")
            return redirect(url_for("franchise_login"))

        # Check if franchise exists, if not create it
        franchise = Franchise.query.filter_by(name=franchise_name).first()
        if not franchise:
            franchise = Franchise(
                name=franchise_name,
                location=franchise_location or "",
            )
            db.session.add(franchise)
            db.session.commit()

        # Create new owner linked to this franchise
        owner = FranchiseOwner(
            name=owner_name,
            email=email,
            franchise_id=franchise.id,
        )
        owner.set_password(password)
        db.session.add(owner)
        db.session.commit()

        flash("Franchise owner account created. Please log in.", "success")
        return redirect(url_for("franchise_login"))

    return render_template("franchise_signup.html")

@app.route("/franchise/logout")
def franchise_logout():
    session.pop("owner_id", None)
    session.pop("franchise_id", None)
    flash("Logged out successfully", "success")
    return redirect(url_for("index"))


@app.route("/franchise/dashboard")
def franchise_dashboard():
    owner_id = session.get("owner_id")
    franchise_id = session.get("franchise_id")

    if not owner_id:
        flash("Please log in as franchise owner", "warning")
        return redirect(url_for("franchise_login"))

    vehicles = Vehicle.query.filter_by(franchise_id=franchise_id).all()
    franchise = Franchise.query.get(franchise_id)
    return render_template(
        "franchise_dashboard.html",
        vehicles=vehicles,
        franchise=franchise,
    )


@app.route("/vehicle/<int:vehicle_id>/edit", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):
    owner_id = session.get("owner_id")
    if not owner_id:
        flash("Please log in as franchise owner", "warning")
        return redirect(url_for("franchise_login"))

    vehicle = Vehicle.query.get_or_404(vehicle_id)
    franchises = Franchise.query.all()

    if request.method == "POST":
        vehicle.registration_number = request.form.get("registration_number")
        vehicle.brand = request.form.get("brand")
        vehicle.model = request.form.get("model")
        issue_date_str = request.form.get("issue_date")
        try:
            vehicle.issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid issue date", "danger")
            return redirect(url_for("edit_vehicle", vehicle_id=vehicle_id))

        vehicle.franchise_id = int(request.form.get("franchise_id"))
        db.session.commit()
        flash("Vehicle updated successfully", "success")
        return redirect(url_for("franchise_dashboard"))

    return render_template(
        "edit_vehicle.html",
        vehicle=vehicle,
        franchises=franchises,
    )


# ---------- Customer View ----------
@app.route("/customer", methods=["GET", "POST"])
def customer_lookup():
    vehicle = None
    if request.method == "POST":
        reg_no = request.form.get("registration_number")
        phone = request.form.get("phone")

        if not (reg_no and phone):
            flash("Please provide both registration number and phone", "warning")
        else:
            vehicle = (
                Vehicle.query.join(Customer)
                .filter(
                    Vehicle.registration_number == reg_no,
                    Customer.phone == phone,
                )
                .first()
            )
            if not vehicle:
                flash("No vehicle found for given details", "warning")

    return render_template("customer_lookup.html", vehicle=vehicle)


if __name__ == "__main__":
    app.run(debug=True)
