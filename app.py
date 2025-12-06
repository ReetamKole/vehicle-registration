import os
import re
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


# Add validation functions
def is_sequential(digits):
    if len(digits) < 4:
        return False
    
    # Check ascending
    ascending = all(int(digits[i]) == int(digits[i-1]) + 1 for i in range(1, len(digits)))
    
    # Check descending
    descending = all(int(digits[i]) == int(digits[i-1]) - 1 for i in range(1, len(digits)))
    
    return ascending or descending

def validate_email(email):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return "Invalid email format."
    
    parts = email.split('@')
    if len(parts) != 2:
        return "Invalid email format."
    
    local, domain = parts
    
    if len(local) == 0 or len(local) > 64:
        return "Email username too long or empty."
    if len(domain) == 0 or len(domain) > 255:
        return "Email domain too long or empty."
    
    suspicious = ['test@test.com', 'admin@admin.com', 'user@user.com', 'example@example.com']
    if email.lower() in suspicious:
        return "This email address is not allowed."
    
    clean_local = re.sub(r'[._-]', '', local)
    unique_chars = len(set(clean_local))
    if unique_chars <= 2 and len(local) > 3:
        return "Email username looks suspicious."
    
    domain_parts = domain.split('.')
    if len(domain_parts) < 2:
        return "Invalid domain format."
    
    tld = domain_parts[-1]
    if len(tld) < 2 or not tld.isalpha():
        return "Invalid domain extension."
    
    return None

def validate_phone(phone):
    digits = re.sub(r'\D', '', phone)
    
    if len(digits) < 7 or len(digits) > 15:
        return "Phone number must be 7-15 digits."
    
    unique_digits = len(set(digits))
    if unique_digits == 1:
        return "Phone number cannot be all same digits."
    
    if is_sequential(digits):
        return "Phone number cannot be sequential digits."
    
    invalid_patterns = ['1234567890', '0987654321']
    if digits in invalid_patterns:
        return "Invalid phone number pattern."
    
    return None

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

        # Collect all errors
        errors = []

        if not (customer_name and customer_email and customer_phone and reg_no and brand and model and issue_date_str):
            errors.append("All fields are required")

        if customer_email:
            # Validate email
            email_error = validate_email(customer_email)
            if email_error:
                errors.append(email_error)

        if customer_phone:
            # Validate phone
            phone_error = validate_phone(customer_phone)
            if phone_error:
                errors.append(phone_error)

        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                
                # Validate date: no future dates
                if issue_date > datetime.now().date():
                    errors.append("Issue date cannot be in the future!")
                
                # Validate date: no dates older than 20 years
                twenty_years_ago = datetime.now().date() - timedelta(days=7300)
                if issue_date < twenty_years_ago:
                    errors.append("Issue date cannot be more than 20 years old!")
                    
            except ValueError:
                errors.append("Invalid issue date format")

        if reg_no:
            # Check if registration number already exists
            existing_vehicle = Vehicle.query.filter_by(registration_number=reg_no).first()
            if existing_vehicle:
                errors.append("Registration Number already exists!")

        # If there are errors, flash them all and return
        if errors:
            for error in errors:
                flash(error, "error")
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
            franchise_id=franchise_id,
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

        # Collect all errors first
        errors = []

        # Validate all fields
        if not (name and email and password and confirm_password and franchise_id and franchise_password):
            errors.append("All fields are required")
        
        if email:
            # Validate email
            email_error = validate_email(email)
            if email_error:
                errors.append(email_error)
            
            # Check if email already exists
            existing_owner = FranchiseOwner.query.filter_by(email=email).first()
            if existing_owner:
                errors.append("Email already registered!")

        # Check password match
        if password and confirm_password and password != confirm_password:
            errors.append("Account passwords do not match!")

        # Verify franchise
        if franchise_id:
            franchise = Franchise.query.get(franchise_id)
            if not franchise:
                errors.append("Invalid franchise selected!")
            elif franchise_password:
                # Check franchise password
                if not check_password_hash(franchise.franchise_password, franchise_password):
                    errors.append("Incorrect franchise password!")

        # If there are errors, flash them all and return with form data
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "franchise_signup.html",
                franchises=franchises,
                name=name,
                email=email,
                password=password,
                confirm_password=confirm_password,
                franchise_id=franchise_id,
                franchise_password=franchise_password
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
    # Check if franchise owner is logged in
    if 'franchise_id' not in session:
        flash("Please login first!", "error")
        return redirect(url_for('franchise_login'))
    
    franchise_id = session.get('franchise_id')
    vehicle = Vehicle.query.get(vehicle_id)
    
    if not vehicle:
        flash("Vehicle not found!", "error")
        return redirect(url_for('franchise_dashboard'))
    
    # Check if this vehicle belongs to the logged-in franchise
    if vehicle.franchise_id != franchise_id:
        flash("You don't have permission to edit this vehicle!", "error")
        return redirect(url_for('franchise_dashboard'))
    
    if request.method == "POST":
        customer_name = request.form.get("customer_name")
        customer_email = request.form.get("customer_email")
        customer_phone = request.form.get("customer_phone")
        registration_number = request.form.get("registration_number")
        brand = request.form.get("brand")
        model = request.form.get("model")
        issue_date_str = request.form.get("issue_date")
        
        # Collect all errors
        errors = []

        if not (customer_name and customer_email and customer_phone and registration_number and brand and model and issue_date_str):
            errors.append("All fields are required")

        if customer_email:
            # Validate email
            email_error = validate_email(customer_email)
            if email_error:
                errors.append(email_error)

        if customer_phone:
            # Validate phone
            phone_error = validate_phone(customer_phone)
            if phone_error:
                errors.append(phone_error)
        
        # Check if registration number is being changed and already exists
        if registration_number and registration_number != vehicle.registration_number:
            existing_vehicle = Vehicle.query.filter_by(registration_number=registration_number).first()
            if existing_vehicle:
                errors.append("Registration Number already exists!")
        
        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                
                # Validate date: no future dates
                if issue_date > datetime.now().date():
                    errors.append("Issue date cannot be in the future!")
                
                # Validate date: no dates older than 20 years
                twenty_years_ago = datetime.now().date() - timedelta(days=7300)
                if issue_date < twenty_years_ago:
                    errors.append("Issue date cannot be more than 20 years old!")
                    
            except ValueError:
                errors.append("Invalid issue date format!")
        
        # If there are errors, flash them all and return with form data
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("edit_vehicle.html", 
                                 vehicle=vehicle,
                                 customer_name=customer_name,
                                 customer_email=customer_email,
                                 customer_phone=customer_phone,
                                 registration_number=registration_number,
                                 brand=brand,
                                 model=model,
                                 issue_date=issue_date_str)
        
        # Update customer details
        vehicle.owner.name = customer_name
        vehicle.owner.email = customer_email
        vehicle.owner.phone = customer_phone
        
        # Update vehicle details
        vehicle.registration_number = registration_number
        vehicle.brand = brand
        vehicle.model = model
        vehicle.issue_date = issue_date
        
        try:
            db.session.commit()
            flash(f"Vehicle {vehicle.registration_number} updated successfully!", "success")
            return redirect(url_for('franchise_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating vehicle: {str(e)}", "error")
    
    return render_template("edit_vehicle.html", vehicle=vehicle)


# ---------- Customer View ----------
@app.route("/customer-lookup", methods=["GET", "POST"])
def customer_lookup():
    if request.method == "POST":
        registration_number = request.form.get("registration_number")
        phone = request.form.get("phone")

        if not registration_number or not phone:
            flash("Both Registration Number and Phone are required!", "error")
            return render_template("customer_lookup.html", 
                                 registration_number=registration_number,
                                 phone=phone)

        # Find vehicle by registration number
        vehicle = Vehicle.query.filter_by(registration_number=registration_number).first()
        
        # Find customer by phone
        customer = Customer.query.filter_by(phone=phone).first()

        # Check what exists and what doesn't
        errors = []
        if not vehicle:
            errors.append("Registration Number does not exist")
        if not customer:
            errors.append("Registered Phone does not exist")
        
        # If either doesn't exist, show specific errors
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("customer_lookup.html",
                                 registration_number=registration_number,
                                 phone=phone)
        
        # Both exist, but check if they match (same vehicle owner)
        if vehicle.owner_id != customer.id:
            flash("Registration Number and Phone do not match the same vehicle!", "error")
            return render_template("customer_lookup.html",
                                 registration_number=registration_number,
                                 phone=phone)

        # Success - show vehicle details
        return render_template("customer_lookup.html", vehicle=vehicle)

    return render_template("customer_lookup.html")


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


@app.route("/owners-list")
def owners_list():
    # Check if franchise owner is logged in
    if 'franchise_id' not in session:
        flash("Please login first!", "error")
        return redirect(url_for('franchise_login'))
    
    franchise_id = session.get('franchise_id')
    franchise = Franchise.query.get(franchise_id)
    
    # Get all franchise owners for this franchise
    owners = FranchiseOwner.query.filter_by(franchise_id=franchise_id).all()
    
    return render_template('owners_list.html', franchise=franchise, owners=owners)


if __name__ == "__main__":
    # host="0.0.0.0" opens the door to the outside world
    app.run(host="0.0.0.0", port=5000, debug=True)
