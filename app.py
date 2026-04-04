import os
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from werkzeug.utils import secure_filename
from models import db, User, CompanyProfile, StudentProfile, PlacementDrive, Application
from forms import LoginForm, StudentRegistrationForm, CompanyRegistrationForm, DriveForm
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- Decorators ---
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role != role:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for('index'))
            if current_user.is_blacklisted:
                logout_user()
                flash("Your account is blacklisted.", "danger")
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Public & Auth Routes ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'company':
            return redirect(url_for('company_dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student_dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if user.is_blacklisted:
                flash("Your account has been blacklisted. Contact admin.", "danger")
                return redirect(url_for('login'))
            if user.role == 'company' and user.company_profile.approval_status != 'Approved':
                flash("Your company account is pending admin approval.", "warning")
                return redirect(url_for('login'))
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = StudentRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered.", "danger")
            return redirect(url_for('register_student'))
        
        filename = None
        if form.resume.data:
            file = form.resume.data
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
        user = User(name=form.name.data, email=form.email.data, role='student')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        student_profile = StudentProfile(
            user_id=user.id,
            phone=form.phone.data,
            department=form.department.data,
            cgpa=form.cgpa.data,
            resume_filename=filename
        )
        db.session.add(student_profile)
        db.session.commit()
        flash("Registration successful! You can now login.", "success")
        return redirect(url_for('login'))
    return render_template('register_student.html', form=form)

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = CompanyRegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered.", "danger")
            return redirect(url_for('register_company'))
        
        user = User(name=form.name.data, email=form.email.data, role='company')
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        company_profile = CompanyProfile(
            user_id=user.id,
            company_name=form.company_name.data,
            hr_contact=form.hr_contact.data,
            website=form.website.data,
            approval_status='Pending'
        )
        db.session.add(company_profile)
        db.session.commit()
        flash("Registration successful! Please wait for admin approval to login.", "info")
        return redirect(url_for('index'))
    return render_template('register_company.html', form=form)

# --- Admin Routes ---
@app.route('/admin')
@role_required('admin')
def admin_dashboard():
    stats = {
        'total_students': StudentProfile.query.count(),
        'total_companies': CompanyProfile.query.count(),
        'total_drives': PlacementDrive.query.count(),
        'total_applications': Application.query.count()
    }
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/companies', methods=['GET'])
@role_required('admin')
def admin_companies():
    search = request.args.get('search', '')
    query = CompanyProfile.query.join(User)
    if search:
        query = query.filter(CompanyProfile.company_name.ilike(f'%{search}%'))
    companies = query.all()
    return render_template('admin/companies.html', companies=companies, search=search)

@app.route('/admin/companies/<int:id>/<action>')
@role_required('admin')
def admin_company_action(id, action):
    company = CompanyProfile.query.get_or_404(id)
    if action == 'approve':
        company.approval_status = 'Approved'
    elif action == 'reject':
        company.approval_status = 'Rejected'
    db.session.commit()
    flash(f"Company {company.company_name} has been {action}d.", "success")
    return redirect(url_for('admin_companies'))

@app.route('/admin/students', methods=['GET'])
@role_required('admin')
def admin_students():
    search = request.args.get('search', '')
    query = StudentProfile.query.join(User)
    if search:
        query = query.filter(
            db.or_(
                User.name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    students = query.all()
    return render_template('admin/students.html', students=students, search=search)

@app.route('/admin/users/<int:id>/toggle_blacklist')
@role_required('admin')
def toggle_blacklist(id):
    user = User.query.get_or_404(id)
    if user.role == 'admin':
        flash("Cannot blacklist admin.", "danger")
        return redirect(request.referrer or url_for('admin_dashboard'))
    user.is_blacklisted = not user.is_blacklisted
    db.session.commit()
    status = "blacklisted" if user.is_blacklisted else "whitelisted"
    flash(f"User {user.email} has been {status}.", "success")
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/drives')
@role_required('admin')
def admin_drives():
    drives = PlacementDrive.query.all()
    return render_template('admin/drives.html', drives=drives)

@app.route('/admin/drives/<int:id>/<action>')
@role_required('admin')
def admin_drive_action(id, action):
    drive = PlacementDrive.query.get_or_404(id)
    if action == 'approve':
        drive.status = 'Approved'
    elif action == 'close':
        drive.status = 'Closed'
    db.session.commit()
    flash(f"Drive for {drive.job_title} has been updated to {drive.status}.", "success")
    return redirect(url_for('admin_drives'))

@app.route('/admin/applications')
@role_required('admin')
def admin_applications():
    page = request.args.get('page', 1, type=int)
    applications = Application.query.order_by(Application.applied_on.desc()).paginate(page=page, per_page=10)
    return render_template('admin/applications.html', applications=applications)

# --- Company Routes ---
@app.route('/company')
@role_required('company')
def company_dashboard():
    drives = PlacementDrive.query.filter_by(company_id=current_user.company_profile.id).all()
    return render_template('company/dashboard.html', drives=drives)

@app.route('/company/drive/new', methods=['GET', 'POST'])
@role_required('company')
def new_drive():
    form = DriveForm()
    if form.validate_on_submit():
        drive = PlacementDrive(
            company_id=current_user.company_profile.id,
            job_title=form.job_title.data,
            job_description=form.job_description.data,
            eligibility=form.eligibility.data,
            deadline=datetime.combine(form.deadline.data, datetime.min.time()),
            status='Pending'
        )
        db.session.add(drive)
        db.session.commit()
        flash("Drive created and pending admin approval.", "success")
        return redirect(url_for('company_dashboard'))
    return render_template('company/new_drive.html', form=form)

@app.route('/company/drive/<int:id>/close')
@role_required('company')
def close_drive(id):
    drive = PlacementDrive.query.filter_by(id=id, company_id=current_user.company_profile.id).first_or_404()
    drive.status = 'Closed'
    db.session.commit()
    flash("Drive closed.", "info")
    return redirect(url_for('company_dashboard'))

@app.route('/company/drive/<int:id>/applicants')
@role_required('company')
def view_applicants(id):
    drive = PlacementDrive.query.filter_by(id=id, company_id=current_user.company_profile.id).first_or_404()
    applications = Application.query.filter_by(drive_id=id).all()
    return render_template('company/applicants.html', drive=drive, applications=applications)

@app.route('/company/application/<int:id>/update/<status>')
@role_required('company')
def update_application_status(id, status):
    if status not in ['Shortlisted', 'Selected', 'Rejected']:
        flash("Invalid status.", "danger")
        return redirect(request.referrer)
    application = Application.query.get_or_404(id)
    if application.drive.company_id != current_user.company_profile.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('company_dashboard'))
    application.status = status
    db.session.commit()
    flash(f"Application status updated to {status}.", "success")
    return redirect(request.referrer)

# --- Student Routes ---
@app.route('/student')
@role_required('student')
def student_dashboard():
    recent_drives = PlacementDrive.query.filter_by(status='Approved').filter(PlacementDrive.deadline >= datetime.utcnow()).order_by(PlacementDrive.created_at.desc()).limit(5).all()
    applications = Application.query.filter_by(student_id=current_user.student_profile.id).all()
    return render_template('student/dashboard.html', recent_drives=recent_drives, applications=applications)

@app.route('/student/drives')
@role_required('student')
def student_drives():
    drives = PlacementDrive.query.filter_by(status='Approved').filter(PlacementDrive.deadline >= datetime.utcnow()).all()
    applied_drive_ids = [app.drive_id for app in current_user.student_profile.applications]
    return render_template('student/drives.html', drives=drives, applied_drive_ids=applied_drive_ids)

@app.route('/student/drive/<int:id>/apply')
@role_required('student')
def apply_drive(id):
    drive = PlacementDrive.query.filter_by(id=id, status='Approved').first_or_404()
    if drive.deadline < datetime.utcnow():
        flash("The deadline for this drive has passed.", "danger")
        return redirect(url_for('student_drives'))
        
    existing_application = Application.query.filter_by(student_id=current_user.student_profile.id, drive_id=id).first()
    if existing_application:
        flash("You have already applied for this drive.", "warning")
        return redirect(url_for('student_drives'))
        
    application = Application(student_id=current_user.student_profile.id, drive_id=id)
    db.session.add(application)
    db.session.commit()
    flash(f"Successfully applied for {drive.job_title} at {drive.company.company_name}.", "success")
    return redirect(url_for('student_dashboard'))

@app.route('/student/applications')
@role_required('student')
def student_applications():
    applications = Application.query.filter_by(student_id=current_user.student_profile.id).order_by(Application.applied_on.desc()).all()
    return render_template('student/applications.html', applications=applications)

# --- API Endpoints (Bonus) ---
@app.route('/api/stats')
def api_stats():
    stats = {
        'total_students': StudentProfile.query.count(),
        'total_companies': CompanyProfile.query.count(),
        'total_drives': PlacementDrive.query.count(),
        'total_applications': Application.query.count()
    }
    return jsonify(stats)

def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        if not User.query.filter_by(email='admin@placement.com').first():
            admin = User(name='Admin', email='admin@placement.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: admin@placement.com / admin123")
            
        # Sample Data Creation
        if not User.query.filter_by(email='company@test.com').first():
            company_user = User(name='Test Company Rep', email='company@test.com', role='company')
            company_user.set_password('company123')
            db.session.add(company_user)
            db.session.commit()
            cp = CompanyProfile(user_id=company_user.id, company_name='Tech Innovators', hr_contact='1234567890', approval_status='Approved')
            db.session.add(cp)
            db.session.commit()
            
            student_user = User(name='John Doe', email='student@test.com', role='student')
            student_user.set_password('student123')
            db.session.add(student_user)
            db.session.commit()
            sp = StudentProfile(user_id=student_user.id, phone='0987654321', department='Computer Science', cgpa=8.5)
            db.session.add(sp)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
