import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Franchise, FranchiseOwner, Customer, Vehicle

app = Flask(__name__)

# --- DB config ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# Fix for some platforms that use postgres:// instead of postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
    # If already logged in, redirect to dashboard
    if session.get('franchise_id'):
        return redirect(url_for('franchise_dashboard'))
    # Otherwise show home page with three options
    return render_template('index.html')


# Add this to make datetime functions available in templates
@app.context_processor
def inject_datetime():
    return {
        'now': datetime.now,
        'timedelta': timedelta
    }


# ---------- Vehicle Registration (Create) ----------
@app.route("/register", methods=["GET", "POST"])
def register_vehicle():
    # Check if franchise owner is logged in
    if 'franchise_id' not in session:
        flash("Please login first!", "error")
        return redirect(url_for('franchise_login'))
    
    franchise_id = session.get('franchise_id')
    franchise = Franchise.query.get(franchise_id)
    
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

        if not (
            customer_name
            and customer_email
            and customer_phone
            and reg_no
            and brand
            and model
            and issue_date_str
        ):
            flash("All fields are required", "danger")
            return redirect(url_for("register_vehicle"))

        try:
            issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
            
            # Validate date: no future dates
            if issue_date > datetime.now().date():
                flash("Issue date cannot be in the future!", "error")
                return render_template(
                    "register_vehicle.html",
                    franchise=franchise,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    registration_number=reg_no,
                    brand=brand,
                    model=model,
                    issue_date=issue_date_str
                )
            
            # Validate date: no dates older than 20 years
            twenty_years_ago = datetime.now().date() - timedelta(days=7300)
            if issue_date < twenty_years_ago:
                flash("Issue date cannot be more than 20 years old!", "error")
                return render_template(
                    "register_vehicle.html",
                    franchise=franchise,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    registration_number=reg_no,
                    brand=brand,
                    model=model,
                    issue_date=issue_date_str
                )
                
        except ValueError:
            flash("Invalid issue date format", "danger")
            return redirect(url_for("register_vehicle"))

        # Check if registration number already exists
        existing_vehicle = Vehicle.query.filter_by(
            registration_number=reg_no
        ).first()
        if existing_vehicle:
            flash("Registration Number already exists!", "error")
            return render_template(
                "register_vehicle.html",
                franchise=franchise,
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                registration_number=reg_no,
                brand=brand,
                model=model,
                issue_date=issue_date_str
            )

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
            franchise_id=franchise_id,  # Use logged-in franchise's ID
            owner_id=customer.id,
        )
        db.session.add(vehicle)
        db.session.commit()

        flash("Vehicle registered successfully!", "success")
        return redirect(url_for("franchise_dashboard"))

    return render_template("register_vehicle.html", franchise=franchise)


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


@app.route("/franchise-signup", methods=["GET", "POST"])
def franchise_signup():
    franchises = Franchise.query.all()
    
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        franchise_id = request.form.get("franchise_id")
        franchise_password = request.form.get("franchise_password")

        # Validate all fields
        if not (name and email and password and confirm_password and franchise_id and franchise_password):
            flash("All fields are required", "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                franchise_id=franchise_id
            )

        # Check password match
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                franchise_id=franchise_id
            )

        # Check if email already exists
        existing_owner = FranchiseOwner.query.filter_by(email=email).first()
        if existing_owner:
            flash("Email already registered!", "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                franchise_id=franchise_id
            )

        # Verify franchise password
        franchise = Franchise.query.get(franchise_id)
        if not franchise:
            flash("Invalid franchise selected!", "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                franchise_id=franchise_id
            )

        if not check_password_hash(franchise.franchise_password, franchise_password):
            flash("Incorrect franchise password!", "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                franchise_id=franchise_id
            )

        # Create new franchise owner
        new_owner = FranchiseOwner(
            name=name,
            email=email,
            password=generate_password_hash(password),
            franchise_id=int(franchise_id)
        )
        
        db.session.add(new_owner)
        db.session.commit()

        flash("Signup successful! Please login.", "success")
        return redirect(url_for("franchise_login"))

    return render_template("franchise_signup.html", franchises=franchises)


@app.route("/franchise-logout")
def franchise_logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('franchise_login'))


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


@app.route("/delete-vehicle/<int:vehicle_id>", methods=["POST"])
def delete_vehicle(vehicle_id):
    # Check if franchise owner is logged in
    if 'franchise_id' not in session:
        flash("Please login first!", "error")
        return redirect(url_for('franchise_login'))
    
    franchise_id = session.get('franchise_id')
    
    # Get the vehicle
    vehicle = Vehicle.query.get(vehicle_id)
    
    if not vehicle:
        flash("Vehicle not found!", "error")
        return redirect(url_for('franchise_dashboard'))
    
    # Check if this vehicle belongs to the logged-in franchise
    if vehicle.franchise_id != franchise_id:
        flash("You don't have permission to delete this vehicle!", "error")
        return redirect(url_for('franchise_dashboard'))
    
    try:
        db.session.delete(vehicle)
        db.session.commit()
        flash(f"Vehicle {vehicle.registration_number} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting vehicle: {str(e)}", "error")
    
    return redirect(url_for('franchise_dashboard'))


if __name__ == "__main__":
    # host="0.0.0.0" opens the door to the outside world
    app.run(host="0.0.0.0", port=5000, debug=True)
