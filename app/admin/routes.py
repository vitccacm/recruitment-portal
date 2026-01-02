import os
import secrets
import string
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from . import bp
from .forms import LoginForm, DepartmentCreateForm, DepartmentEditForm, AccountForm, RoundForm
from ..models import db, Admin, Department, Application, Student, Round, RoundDepartment, RoundCandidate, SiteSettings, ProfileField, DepartmentQuestion


def admin_required(f):
    """Decorator to ensure user is an admin (any role)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Admin):
            flash('Access denied. Admins only.', 'error')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """Decorator to ensure user is a super admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Admin):
            flash('Access denied. Admins only.', 'error')
            return redirect(url_for('admin.login'))
        if not current_user.is_super_admin:
            flash('Access denied. Super admin privileges required.', 'error')
            return redirect(url_for('admin.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def generate_password(length=12):
    """Generate a random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@bp.route('/', methods=['GET', 'POST'])
@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login"""
    if current_user.is_authenticated and isinstance(current_user, Admin):
        if current_user.is_dept_admin:
            return redirect(url_for('dept.dashboard'))
        return redirect(url_for('admin.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        admin = Admin.query.filter_by(email=form.email.data).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            flash(f'Welcome back, {admin.name or "Admin"}!', 'success')
            if admin.is_dept_admin:
                return redirect(url_for('dept.dashboard'))
            return redirect(url_for('admin.dashboard'))
        flash('Invalid email or password.', 'error')
    
    return render_template('admin/login.html', form=form)


@bp.route('/logout')
@login_required
@admin_required
def logout():
    """Admin logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin.login'))


@bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """Admin dashboard with stats"""
    stats = {
        'total_students': Student.query.count(),
        'total_departments': Department.query.count(),
        'active_departments': Department.query.filter_by(is_active=True).count(),
        'total_applications': Application.query.count(),
        'pending_applications': Application.query.filter_by(status='pending').count(),
        'total_admins': Admin.query.filter_by(role='admin').count(),
        'total_dept_admins': Admin.query.filter_by(role='dept-admin').count(),
    }
    recent_applications = Application.query.order_by(Application.applied_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_applications=recent_applications)


@bp.route('/departments')
@login_required
@super_admin_required
def departments():
    """List all departments"""
    departments = Department.query.order_by(Department.created_at.desc()).all()
    return render_template('admin/departments.html', departments=departments)


@bp.route('/departments/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def add_department():
    """Quick create department with just name"""
    form = DepartmentCreateForm()
    if form.validate_on_submit():
        department = Department(name=form.name.data, is_active=False)
        db.session.add(department)
        db.session.commit()
        flash(f'Department "{department.name}" created! Now add more details.', 'success')
        return redirect(url_for('admin.edit_department', dept_id=department.id))
    
    return render_template('admin/department_create.html', form=form)


@bp.route('/department/<int:dept_id>')
@login_required
@super_admin_required
def department_detail(dept_id):
    """View department details"""
    department = Department.query.get_or_404(dept_id)
    applications = Application.query.filter_by(department_id=dept_id).order_by(Application.applied_at.desc()).all()
    return render_template('admin/department_detail.html', department=department, applications=applications)


@bp.route('/departments/edit/<int:dept_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_department(dept_id):
    """Edit department details"""
    department = Department.query.get_or_404(dept_id)
    form = DepartmentEditForm(obj=department)
    
    if form.validate_on_submit():
        department.name = form.name.data
        department.short_description = form.short_description.data
        department.description = form.description.data
        department.positions = form.positions.data
        department.requirements = form.requirements.data
        department.recruitment_start = form.recruitment_start.data
        department.recruitment_end = form.recruitment_end.data
        department.is_active = form.is_active.data
        
        # Handle image upload
        if form.image.data:
            file = form.image.data
            filename = secure_filename(f"dept_{department.id}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            department.image_path = f"uploads/{filename}"
        
        db.session.commit()
        flash('Department updated successfully!', 'success')
        return redirect(url_for('admin.department_detail', dept_id=dept_id))
    
    return render_template('admin/department_edit.html', form=form, department=department)


@bp.route('/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_department(dept_id):
    """Delete a department"""
    department = Department.query.get_or_404(dept_id)
    
    # Delete associated applications first
    Application.query.filter_by(department_id=dept_id).delete()
    
    db.session.delete(department)
    db.session.commit()
    flash(f'Department "{department.name}" deleted.', 'success')
    return redirect(url_for('admin.departments'))


@bp.route('/departments/<int:dept_id>/toggle', methods=['POST'])
@login_required
@super_admin_required
def toggle_department(dept_id):
    """Toggle department active status"""
    department = Department.query.get_or_404(dept_id)
    department.is_active = not department.is_active
    db.session.commit()
    status = 'activated' if department.is_active else 'deactivated'
    flash(f'Department "{department.name}" {status}.', 'success')
    return redirect(url_for('admin.departments'))


@bp.route('/applications')
@login_required
@super_admin_required
def applications():
    """View all applications with filters"""
    status_filter = request.args.get('status', '')
    dept_filter = request.args.get('department', '')
    
    query = Application.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    if dept_filter:
        query = query.filter_by(department_id=int(dept_filter))
    
    applications = query.order_by(Application.applied_at.desc()).all()
    departments = Department.query.all()
    
    return render_template('admin/applications.html', 
                         applications=applications,
                         departments=departments,
                         current_status=status_filter,
                         current_dept=dept_filter)


@bp.route('/applications/<int:app_id>/status/<status>', methods=['POST'])
@login_required
@super_admin_required
def update_application_status(app_id, status):
    """Update application status"""
    if status not in ['pending', 'accepted', 'rejected']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.applications'))
    
    application = Application.query.get_or_404(app_id)
    application.status = status
    db.session.commit()
    flash(f'Application status updated to {status}.', 'success')
    return redirect(url_for('admin.applications'))


# ============ ACCOUNTS MANAGEMENT ============

@bp.route('/accounts')
@login_required
@super_admin_required
def accounts():
    """List all admin accounts"""
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template('admin/accounts.html', admins=admins)


@bp.route('/accounts/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def add_account():
    """Add a new admin or dept-admin account"""
    form = AccountForm()
    departments = Department.query.all()
    
    if form.validate_on_submit():
        # Check if email already exists
        if Admin.query.filter_by(email=form.email.data).first():
            flash('An account with this email already exists.', 'error')
            return render_template('admin/account_form.html', form=form, departments=departments)
        
        # Generate or use provided password
        if form.generate_password.data:
            password = generate_password()
        else:
            password = form.password.data
            if not password:
                flash('Please provide a password or check "Generate Random Password".', 'error')
                return render_template('admin/account_form.html', form=form, departments=departments)
        
        # Get role and department
        role = request.form.get('role', 'admin')
        dept_id = request.form.get('department_id') if role == 'dept-admin' else None
        
        # Create admin
        admin = Admin(
            email=form.email.data,
            name=form.name.data,
            role=role,
            department_id=int(dept_id) if dept_id else None
        )
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        # Show the generated password
        if form.generate_password.data:
            flash(f'Account created! Generated password: {password}', 'success')
        else:
            flash('Account created successfully!', 'success')
        
        return redirect(url_for('admin.accounts'))
    
    return render_template('admin/account_form.html', form=form, departments=departments)


@bp.route('/accounts/edit/<int:admin_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_account(admin_id):
    """Edit an admin account"""
    admin = Admin.query.get_or_404(admin_id)
    
    # Prevent editing the default admin
    if admin.email == 'admin' and admin.id == 1:
        flash('Cannot edit the default admin account.', 'error')
        return redirect(url_for('admin.accounts'))
    
    form = AccountForm(obj=admin)
    departments = Department.query.all()
    
    if form.validate_on_submit():
        # Check if email changed and already exists
        if form.email.data != admin.email and Admin.query.filter_by(email=form.email.data).first():
            flash('An account with this email already exists.', 'error')
            return render_template('admin/account_form.html', form=form, admin=admin, departments=departments)
        
        admin.name = form.name.data
        admin.email = form.email.data
        admin.role = request.form.get('role', 'admin')
        admin.department_id = int(request.form.get('department_id')) if admin.role == 'dept-admin' and request.form.get('department_id') else None
        
        # Update password if provided
        if form.generate_password.data:
            password = generate_password()
            admin.set_password(password)
            flash(f'Password updated! New password: {password}', 'success')
        elif form.password.data:
            admin.set_password(form.password.data)
            flash('Password updated!', 'info')
        
        db.session.commit()
        flash('Account updated successfully!', 'success')
        return redirect(url_for('admin.accounts'))
    
    return render_template('admin/account_form.html', form=form, admin=admin, departments=departments)


@bp.route('/accounts/delete/<int:admin_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_account(admin_id):
    """Delete an admin account"""
    admin = Admin.query.get_or_404(admin_id)
    
    # Prevent deleting yourself or the default admin
    if admin.id == current_user.id:
        flash('Cannot delete your own account.', 'error')
        return redirect(url_for('admin.accounts'))
    
    if admin.email == 'admin' and admin.id == 1:
        flash('Cannot delete the default admin account.', 'error')
        return redirect(url_for('admin.accounts'))
    
    db.session.delete(admin)
    db.session.commit()
    flash(f'Account "{admin.email}" deleted.', 'success')
    return redirect(url_for('admin.accounts'))


# ============ ROUNDS MANAGEMENT ============

@bp.route('/rounds')
@login_required
@super_admin_required
def rounds():
    """List all rounds"""
    rounds = Round.query.order_by(Round.order, Round.created_at.desc()).all()
    return render_template('admin/rounds.html', rounds=rounds)


@bp.route('/rounds/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def add_round():
    """Create a new round"""
    form = RoundForm()
    
    # Populate prerequisite choices
    existing_rounds = Round.query.order_by(Round.order).all()
    form.prerequisite_id.choices = [(0, 'No prerequisite')] + [(r.id, r.name) for r in existing_rounds]
    
    if form.validate_on_submit():
        round_obj = Round(
            name=form.name.data,
            description=form.description.data,
            prerequisite_id=form.prerequisite_id.data if form.prerequisite_id.data else None,
            is_visible_before_results=form.is_visible_before_results.data,
            order=form.order.data or 0
        )
        db.session.add(round_obj)
        db.session.commit()
        
        # Create RoundDepartment entries for all departments
        departments = Department.query.all()
        for dept in departments:
            rd = RoundDepartment(round_id=round_obj.id, department_id=dept.id)
            db.session.add(rd)
        db.session.commit()
        
        flash(f'Round "{round_obj.name}" created successfully!', 'success')
        return redirect(url_for('admin.round_detail', round_id=round_obj.id))
    
    return render_template('admin/round_form.html', form=form)


@bp.route('/rounds/<int:round_id>')
@login_required
@super_admin_required
def round_detail(round_id):
    """View round details with department statuses"""
    round_obj = Round.query.get_or_404(round_id)
    
    # Get department states
    dept_states = RoundDepartment.query.filter_by(round_id=round_id).all()
    
    # Stats per department
    dept_stats = []
    for rd in dept_states:
        candidates = RoundCandidate.query.join(Application).filter(
            RoundCandidate.round_id == round_id,
            Application.department_id == rd.department_id
        ).all()
        
        dept_stats.append({
            'department': rd.department,
            'state': rd,
            'total': len(candidates),
            'selected': len([c for c in candidates if c.status == 'selected']),
            'pending': len([c for c in candidates if c.status == 'pending']),
            'not_selected': len([c for c in candidates if c.status == 'not_selected']),
        })
    
    return render_template('admin/round_detail.html', round=round_obj, dept_stats=dept_stats)


@bp.route('/rounds/<int:round_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_round(round_id):
    """Edit a round"""
    round_obj = Round.query.get_or_404(round_id)
    form = RoundForm(obj=round_obj)
    
    # Populate prerequisite choices (exclude self and dependents)
    existing_rounds = Round.query.filter(Round.id != round_id).order_by(Round.order).all()
    form.prerequisite_id.choices = [(0, 'No prerequisite')] + [(r.id, r.name) for r in existing_rounds]
    
    if form.validate_on_submit():
        round_obj.name = form.name.data
        round_obj.description = form.description.data
        round_obj.prerequisite_id = form.prerequisite_id.data if form.prerequisite_id.data else None
        round_obj.is_visible_before_results = form.is_visible_before_results.data
        round_obj.order = form.order.data or 0
        
        db.session.commit()
        flash('Round updated successfully!', 'success')
        return redirect(url_for('admin.round_detail', round_id=round_id))
    
    # Pre-select prerequisite
    if round_obj.prerequisite_id:
        form.prerequisite_id.data = round_obj.prerequisite_id
    
    return render_template('admin/round_form.html', form=form, round=round_obj)


@bp.route('/rounds/<int:round_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_round(round_id):
    """Delete a round"""
    round_obj = Round.query.get_or_404(round_id)
    name = round_obj.name
    
    # Check for dependent rounds
    if round_obj.dependent_rounds:
        flash(f'Cannot delete. Other rounds depend on "{name}".', 'error')
        return redirect(url_for('admin.rounds'))
    
    db.session.delete(round_obj)
    db.session.commit()
    flash(f'Round "{name}" deleted.', 'success')
    return redirect(url_for('admin.rounds'))


@bp.route('/rounds/<int:round_id>/dept/<int:dept_id>/toggle-lock', methods=['POST'])
@login_required
@super_admin_required
def toggle_round_lock(round_id, dept_id):
    """Toggle lock status for a department in a round"""
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    rd.is_locked = not rd.is_locked
    db.session.commit()
    status = 'locked' if rd.is_locked else 'unlocked'
    flash(f'Round {status} for {rd.department.name}.', 'success')
    return redirect(url_for('admin.round_detail', round_id=round_id))


@bp.route('/rounds/<int:round_id>/dept/<int:dept_id>/toggle-release', methods=['POST'])
@login_required
@super_admin_required
def toggle_round_release(round_id, dept_id):
    """Toggle results release for a department in a round"""
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    rd.results_released = not rd.results_released
    db.session.commit()
    status = 'released' if rd.results_released else 'hidden'
    flash(f'Results {status} for {rd.department.name}.', 'success')
    return redirect(url_for('admin.round_detail', round_id=round_id))


@bp.route('/rounds/<int:round_id>/dept/<int:dept_id>/toggle-notes', methods=['POST'])
@login_required
@super_admin_required
def toggle_notes_public(round_id, dept_id):
    """Toggle notes visibility for a department in a round"""
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    rd.notes_public = not rd.notes_public
    db.session.commit()
    status = 'public' if rd.notes_public else 'hidden'
    flash(f'Notes now {status} for {rd.department.name}.', 'success')
    return redirect(url_for('admin.round_detail', round_id=round_id))


# ============ SETTINGS ============

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@super_admin_required
def settings():
    """Admin settings page"""
    if request.method == 'POST':
        # Update auth settings
        SiteSettings.set('allow_signup', 'true' if request.form.get('allow_signup') else 'false')
        SiteSettings.set('allow_google', 'true' if request.form.get('allow_google') else 'false')
        SiteSettings.set('allow_email', 'true' if request.form.get('allow_email') else 'false')
        SiteSettings.set('allowed_domains', request.form.get('allowed_domains', '').strip())
        
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    current_settings = {
        'allow_signup': SiteSettings.get_bool('allow_signup', True),
        'allow_google': SiteSettings.get_bool('allow_google', True),
        'allow_email': SiteSettings.get_bool('allow_email', True),
        'allowed_domains': SiteSettings.get('allowed_domains', ''),
    }
    
    return render_template('admin/settings.html', settings=current_settings)


# ============ PROFILE FIELDS ============

@bp.route('/profile-fields')
@login_required
@super_admin_required
def profile_fields():
    """Manage custom profile fields"""
    fields = ProfileField.query.order_by(ProfileField.order).all()
    return render_template('admin/profile_fields.html', fields=fields)


@bp.route('/profile-fields/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def add_profile_field():
    """Add a new profile field"""
    if request.method == 'POST':
        field = ProfileField(
            field_name=request.form.get('field_name', '').strip().lower().replace(' ', '_'),
            label=request.form.get('label', '').strip(),
            field_type=request.form.get('field_type', 'text'),
            options=request.form.get('options', ''),
            is_required='is_required' in request.form,
            is_enabled='is_enabled' in request.form,
            order=int(request.form.get('order', 0))
        )
        db.session.add(field)
        db.session.commit()
        flash('Profile field added!', 'success')
        return redirect(url_for('admin.profile_fields'))
    
    return render_template('admin/profile_field_form.html', field=None)


@bp.route('/profile-fields/<int:field_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_profile_field(field_id):
    """Edit a profile field"""
    field = ProfileField.query.get_or_404(field_id)
    
    if request.method == 'POST':
        field.field_name = request.form.get('field_name', '').strip().lower().replace(' ', '_')
        field.label = request.form.get('label', '').strip()
        field.field_type = request.form.get('field_type', 'text')
        field.options = request.form.get('options', '')
        field.is_required = 'is_required' in request.form
        field.is_enabled = 'is_enabled' in request.form
        field.order = int(request.form.get('order', 0))
        db.session.commit()
        flash('Profile field updated!', 'success')
        return redirect(url_for('admin.profile_fields'))
    
    return render_template('admin/profile_field_form.html', field=field)


@bp.route('/profile-fields/<int:field_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_profile_field(field_id):
    """Delete a profile field"""
    field = ProfileField.query.get_or_404(field_id)
    db.session.delete(field)
    db.session.commit()
    flash('Profile field deleted.', 'success')
    return redirect(url_for('admin.profile_fields'))


# ============ DEPARTMENT QUESTIONS (ADMIN) ============

@bp.route('/questions')
@login_required
@super_admin_required
def questions():
    """View all departments for question management"""
    departments = Department.query.order_by(Department.name).all()
    return render_template('admin/questions.html', departments=departments)


@bp.route('/questions/<int:dept_id>')
@login_required
@super_admin_required
def dept_questions(dept_id):
    """Manage questions for a specific department"""
    department = Department.query.get_or_404(dept_id)
    questions = DepartmentQuestion.query.filter_by(department_id=dept_id).order_by(DepartmentQuestion.order).all()
    return render_template('admin/dept_questions.html', department=department, questions=questions)


@bp.route('/questions/<int:dept_id>/add', methods=['GET', 'POST'])
@login_required
@super_admin_required
def add_dept_question(dept_id):
    """Add a question to a department"""
    department = Department.query.get_or_404(dept_id)
    
    if request.method == 'POST':
        q = DepartmentQuestion(
            department_id=dept_id,
            question_text=request.form.get('question_text', '').strip(),
            question_type=request.form.get('question_type', 'text'),
            options=request.form.get('options', ''),
            is_required='is_required' in request.form,
            file_max_size=int(request.form.get('file_max_size', 1024)),
            allowed_extensions=request.form.get('allowed_extensions', 'pdf'),
            order=int(request.form.get('order', 0))
        )
        db.session.add(q)
        db.session.commit()
        flash('Question added!', 'success')
        return redirect(url_for('admin.dept_questions', dept_id=dept_id))
    
    return render_template('admin/dept_question_form.html', department=department, question=None)


@bp.route('/questions/<int:dept_id>/<int:q_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_dept_question(dept_id, q_id):
    """Edit a department question"""
    department = Department.query.get_or_404(dept_id)
    q = DepartmentQuestion.query.get_or_404(q_id)
    
    if request.method == 'POST':
        q.question_text = request.form.get('question_text', '').strip()
        q.question_type = request.form.get('question_type', 'text')
        q.options = request.form.get('options', '')
        q.is_required = 'is_required' in request.form
        q.file_max_size = int(request.form.get('file_max_size', 1024))
        q.allowed_extensions = request.form.get('allowed_extensions', 'pdf')
        q.order = int(request.form.get('order', 0))
        db.session.commit()
        flash('Question updated!', 'success')
        return redirect(url_for('admin.dept_questions', dept_id=dept_id))
    
    return render_template('admin/dept_question_form.html', department=department, question=q)


@bp.route('/questions/<int:dept_id>/<int:q_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_dept_question(dept_id, q_id):
    """Delete a department question"""
    q = DepartmentQuestion.query.get_or_404(q_id)
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted.', 'success')
    return redirect(url_for('admin.dept_questions', dept_id=dept_id))


# ============ APPLICANT DETAIL VIEW ============

@bp.route('/applicant/<int:app_id>')
@login_required
@admin_required
def applicant_detail(app_id):
    """View detailed applicant information"""
    from ..models import QuestionResponse
    application = Application.query.get_or_404(app_id)
    
    # Check permission for dept admin
    if current_user.role == 'dept_admin' and current_user.department_id != application.department_id:
        flash('Access denied. You can only view applicants for your department.', 'error')
        return redirect(url_for('admin.dashboard'))
        
    student = application.student
    
    # Get question responses for this application
    responses = QuestionResponse.query.filter_by(application_id=app_id).all()
    response_dict = {r.question_id: r for r in responses}
    
    # Get custom questions for this department
    questions = DepartmentQuestion.query.filter_by(department_id=application.department_id).order_by(DepartmentQuestion.order).all()
    
    # Parse extra_data
    extra_data = {}
    if student.extra_data:
        try:
            extra_data = eval(student.extra_data)
        except:
            pass
    
    return render_template('admin/applicant_detail.html', 
                         application=application, 
                         student=student,
                         questions=questions,
                         responses=response_dict,
                         extra_data=extra_data)


@bp.route('/round/<int:round_id>/dept/<int:dept_id>/candidates')
@login_required
@super_admin_required
def round_candidates(round_id, dept_id):
    """View candidates for a specific round and department"""
    round_obj = Round.query.get_or_404(round_id)
    department = Department.query.get_or_404(dept_id)
    
    # Get round-department state
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first()
    
    # Get eligible applications (improved logic could go here)
    # For now, roughly same as dept logic
    if round_obj.prerequisite_id:
        # Get apps passed in prerequisite
        prev_round_candidates = RoundCandidate.query.join(Application).filter(
            RoundCandidate.round_id == round_obj.prerequisite_id,
            RoundCandidate.status == 'selected',
            Application.department_id == dept_id
        ).all()
        eligible_app_ids = [rc.application_id for rc in prev_round_candidates]
        eligible_apps = Application.query.filter(Application.id.in_(eligible_app_ids)).all()
    else:
        # First round - all dept applications
        eligible_apps = Application.query.filter_by(department_id=dept_id).all()

    # Get current candidates status
    candidates = RoundCandidate.query.filter_by(round_id=round_id).all()
    candidates_dict = {c.application_id: c for c in candidates}
    
    return render_template('admin/round_candidates.html', 
                         round=round_obj, 
                         department=department,
                         state=rd,
                         eligible_apps=eligible_apps, 
                         candidates=candidates_dict)
