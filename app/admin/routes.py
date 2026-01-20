import os
import secrets
import string
import json
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from . import bp
from .forms import LoginForm, DepartmentCreateForm, DepartmentEditForm, AccountForm, RoundForm
from ..models import db, Admin, Department, Application, Student, Round, RoundDepartment, RoundCandidate, SiteSettings, ProfileField, DepartmentQuestion, Membership, QuestionResponse, ActionLog, PageVisit


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
            ActionLog.log(
                action='login',
                area='auth',
                details={'email': admin.email, 'role': admin.role},
                user=admin
            )
            flash(f'Welcome back, {admin.name or "Admin"}!', 'success')
            if admin.is_dept_admin:
                return redirect(url_for('dept.dashboard'))
            return redirect(url_for('admin.dashboard'))
        # Log failed login attempt
        ActionLog.log(
            action='login_failed',
            area='auth',
            details={'attempted_email': form.email.data}
        )
        flash('Invalid email or password.', 'error')
    
    return render_template('admin/login.html', form=form)


@bp.route('/logout')
@login_required
@admin_required
def logout():
    """Admin logout"""
    ActionLog.log(
        action='logout',
        area='auth',
        details={'email': current_user.email}
    )
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


@bp.route('/analytics')
@login_required
@super_admin_required
def analytics():
    """Analytics dashboard - HTML shell with skeleton loaders"""
    return render_template('admin/analytics.html')


@bp.route('/api/analytics')
@login_required
@super_admin_required
def api_analytics():
    """API endpoint returning all analytics data as JSON"""
    from datetime import datetime, timedelta
    from flask import jsonify
    from sqlalchemy import func
    
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    
    # Overview Stats
    all_students = Student.query.all()
    complete_profiles = [s for s in all_students if s.profile_completion >= 75]
    students_with_apps = db.session.query(Application.student_id).distinct().count()
    
    overview = {
        'total_students': len(all_students),
        'students_today': Student.query.filter(func.date(Student.created_at) == today).count(),
        'total_applications': Application.query.count(),
        'applications_today': Application.query.filter(func.date(Application.applied_at) == today).count(),
        'pending_applications': Application.query.filter_by(status='pending').count(),
        'total_memberships': Membership.query.count(),
        'memberships_today': Membership.query.filter(func.date(Membership.created_at) == today).count(),
        'active_departments': Department.query.filter_by(is_active=True).count(),
        'total_admins': Admin.query.count(),
    }
    
    # Applications by Department
    dept_apps = db.session.query(
        Department.name,
        func.count(Application.id)
    ).outerjoin(Application).group_by(Department.id).all()
    
    applications_by_dept = {
        'labels': [d[0] for d in dept_apps],
        'values': [d[1] for d in dept_apps]
    }
    
    # Application Status Distribution
    application_status = {
        'pending': Application.query.filter_by(status='pending').count(),
        'accepted': Application.query.filter_by(status='accepted').count(),
        'rejected': Application.query.filter_by(status='rejected').count(),
    }
    
    # Signups Trend (last 7 days)
    signups_trend = {'labels': [], 'students': [], 'memberships': []}
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        signups_trend['labels'].append(day.strftime('%b %d'))
        signups_trend['students'].append(
            Student.query.filter(func.date(Student.created_at) == day).count()
        )
        signups_trend['memberships'].append(
            Membership.query.filter(func.date(Membership.created_at) == day).count()
        )
    
    # Top Admins by Activity (last 7 days)
    top_admins = db.session.query(
        ActionLog.user_email,
        func.count(ActionLog.id)
    ).filter(
        ActionLog.user_type == 'admin',
        ActionLog.timestamp >= datetime.combine(week_ago, datetime.min.time())
    ).group_by(ActionLog.user_email).order_by(func.count(ActionLog.id).desc()).limit(5).all()
    
    top_admins_data = [{'email': a[0], 'count': a[1]} for a in top_admins if a[0]]
    
    # Membership Stats
    membership_stats = {
        'total': Membership.query.count(),
        'pending': Membership.query.filter_by(is_archived=False).count(),
        'approved': Membership.query.filter_by(is_archived=True).count(),
    }
    
    # Student Stats
    student_stats = {
        'total': len(all_students),
        'complete_profiles': len(complete_profiles),
        'applied': students_with_apps,
    }
    
    # Log Stats
    log_stats = {
        'today': ActionLog.query.filter(func.date(ActionLog.timestamp) == today).count(),
        'this_week': ActionLog.query.filter(ActionLog.timestamp >= datetime.combine(week_ago, datetime.min.time())).count(),
        'logins_today': ActionLog.query.filter(
            func.date(ActionLog.timestamp) == today,
            ActionLog.action == 'login'
        ).count(),
        'failed_logins': ActionLog.query.filter(
            ActionLog.timestamp >= datetime.combine(week_ago, datetime.min.time()),
            ActionLog.action == 'login_failed'
        ).count(),
    }
    
    # Page Visit Stats
    total_visits = PageVisit.query.count()
    visits_today = PageVisit.query.filter(func.date(PageVisit.timestamp) == today).count()
    visits_week = PageVisit.query.filter(PageVisit.timestamp >= datetime.combine(week_ago, datetime.min.time())).count()
    
    # Top pages visited
    top_pages = db.session.query(
        PageVisit.page_name,
        func.count(PageVisit.id)
    ).group_by(PageVisit.page_name).order_by(func.count(PageVisit.id).desc()).limit(10).all()
    
    page_visits = {
        'total': total_visits,
        'today': visits_today,
        'this_week': visits_week,
        'top_pages': [{'page': p[0], 'count': p[1]} for p in top_pages]
    }
    
    return jsonify({
        'overview': overview,
        'applications_by_dept': applications_by_dept,
        'application_status': application_status,
        'signups_trend': signups_trend,
        'top_admins': top_admins_data,
        'membership_stats': membership_stats,
        'student_stats': student_stats,
        'log_stats': log_stats,
        'page_visits': page_visits,
    })

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
        ActionLog.log(
            action='create_department',
            area='departments',
            details={'department_id': department.id, 'name': department.name}
        )
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
        ActionLog.log(
            action='update_department',
            area='departments',
            details={'department_id': department.id, 'name': department.name}
        )
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
    
    dept_name = department.name
    db.session.delete(department)
    db.session.commit()
    ActionLog.log(
        action='delete_department',
        area='departments',
        details={'department_id': dept_id, 'name': dept_name}
    )
    flash(f'Department "{dept_name}" deleted.', 'success')
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
    ActionLog.log(
        action='toggle_department',
        area='departments',
        details={'department_id': dept_id, 'name': department.name, 'is_active': department.is_active}
    )
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
    old_status = application.status
    application.status = status
    db.session.commit()
    ActionLog.log(
        action='update_application_status',
        area='applications',
        details={
            'application_id': app_id,
            'student_email': application.student.email,
            'department': application.department.name,
            'old_status': old_status,
            'new_status': status
        }
    )
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
        
        ActionLog.log(
            action='create_account',
            area='accounts',
            details={'account_id': admin.id, 'email': admin.email, 'role': role}
        )
        
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
        ActionLog.log(
            action='update_account',
            area='accounts',
            details={'account_id': admin.id, 'email': admin.email, 'role': admin.role}
        )
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
    
    admin_email = admin.email
    db.session.delete(admin)
    db.session.commit()
    ActionLog.log(
        action='delete_account',
        area='accounts',
        details={'account_id': admin_id, 'email': admin_email}
    )
    flash(f'Account "{admin_email}" deleted.', 'success')
    return redirect(url_for('admin.accounts'))


@bp.route('/accounts/<int:admin_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_account_password(admin_id):
    """Reset password for an admin account"""
    admin = Admin.query.get_or_404(admin_id)
    
    # Prevent resetting default admin password via this route
    if admin.email == 'admin' and admin.id == 1:
        flash('Cannot reset default admin password. Use manage_db.py instead.', 'error')
        return redirect(url_for('admin.accounts'))
    
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    
    if not new_password or len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin.accounts'))
    
    if new_password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('admin.accounts'))
    
    admin.set_password(new_password)
    db.session.commit()
    ActionLog.log(
        action='reset_password',
        area='accounts',
        details={'account_id': admin_id, 'email': admin.email}
    )
    flash(f'Password reset for "{admin.email}".', 'success')
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
        
        ActionLog.log(
            action='create_round',
            area='rounds',
            details={'round_id': round_obj.id, 'name': round_obj.name}
        )
        
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
        ActionLog.log(
            action='update_round',
            area='rounds',
            details={'round_id': round_id, 'name': round_obj.name}
        )
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
    ActionLog.log(
        action='delete_round',
        area='rounds',
        details={'round_id': round_id, 'name': name}
    )
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
    ActionLog.log(
        action='toggle_round_lock',
        area='rounds',
        details={'round_id': round_id, 'department': rd.department.name, 'is_locked': rd.is_locked}
    )
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
    ActionLog.log(
        action='toggle_results_release',
        area='rounds',
        details={'round_id': round_id, 'department': rd.department.name, 'results_released': rd.results_released}
    )
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
    ActionLog.log(
        action='toggle_notes_visibility',
        area='rounds',
        details={'round_id': round_id, 'department': rd.department.name, 'notes_public': rd.notes_public}
    )
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
        
        ActionLog.log(
            action='update_settings',
            area='settings',
            details={
                'allow_signup': request.form.get('allow_signup') is not None,
                'allow_google': request.form.get('allow_google') is not None,
                'allow_email': request.form.get('allow_email') is not None,
                'allowed_domains': request.form.get('allowed_domains', '').strip()
            }
        )
        
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
        ActionLog.log(
            action='create_profile_field',
            area='profile_fields',
            details={'field_id': field.id, 'field_name': field.field_name, 'label': field.label}
        )
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
        ActionLog.log(
            action='update_profile_field',
            area='profile_fields',
            details={'field_id': field.id, 'field_name': field.field_name, 'label': field.label}
        )
        flash('Profile field updated!', 'success')
        return redirect(url_for('admin.profile_fields'))
    
    return render_template('admin/profile_field_form.html', field=field)


@bp.route('/profile-fields/<int:field_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_profile_field(field_id):
    """Delete a profile field"""
    field = ProfileField.query.get_or_404(field_id)
    field_name = field.field_name
    db.session.delete(field)
    db.session.commit()
    ActionLog.log(
        action='delete_profile_field',
        area='profile_fields',
        details={'field_id': field_id, 'field_name': field_name}
    )
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
        ActionLog.log(
            action='create_question',
            area='questions',
            details={'question_id': q.id, 'department': department.name, 'question_type': q.question_type}
        )
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
        ActionLog.log(
            action='update_question',
            area='questions',
            details={'question_id': q.id, 'department': department.name}
        )
        flash('Question updated!', 'success')
        return redirect(url_for('admin.dept_questions', dept_id=dept_id))
    
    return render_template('admin/dept_question_form.html', department=department, question=q)


@bp.route('/questions/<int:dept_id>/<int:q_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_dept_question(dept_id, q_id):
    """Delete a department question"""
    q = DepartmentQuestion.query.get_or_404(q_id)
    department = Department.query.get(dept_id)
    db.session.delete(q)
    db.session.commit()
    ActionLog.log(
        action='delete_question',
        area='questions',
        details={'question_id': q_id, 'department': department.name if department else 'Unknown'}
    )
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


# ============ STUDENTS MANAGEMENT ============

@bp.route('/students')
@login_required
@super_admin_required
def students():
    """View all signed up students"""
    status_filter = request.args.get('status', 'all')
    
    query = Student.query
    
    # Filter based on profile completion
    all_students = Student.query.all()
    complete_students = [s for s in all_students if s.profile_completion >= 75]
    incomplete_students = [s for s in all_students if s.profile_completion < 75]
    
    if status_filter == 'complete':
        students = complete_students
    elif status_filter == 'incomplete':
        students = incomplete_students
    else:
        students = all_students
    
    # Sort by created_at descending
    students = sorted(students, key=lambda x: x.created_at, reverse=True)
    
    counts = {
        'total': len(all_students),
        'complete': len(complete_students),
        'incomplete': len(incomplete_students)
    }
    
    return render_template('admin/students.html', 
                         students=students,
                         current_status=status_filter,
                         counts=counts)


# ============ MEMBERSHIPS MANAGEMENT ============

@bp.route('/memberships')
@login_required
@super_admin_required
def memberships():
    """View all membership signups"""
    status_filter = request.args.get('status', 'all')
    
    query = Membership.query
    
    if status_filter == 'pending':
        query = query.filter_by(is_archived=False)
    elif status_filter == 'archived':
        query = query.filter_by(is_archived=True)
    
    memberships = query.order_by(Membership.created_at.desc()).all()
    
    # Get counts for tabs
    counts = {
        'all': Membership.query.count(),
        'pending': Membership.query.filter_by(is_archived=False).count(),
        'archived': Membership.query.filter_by(is_archived=True).count()
    }
    
    return render_template('admin/memberships.html', 
                         memberships=memberships,
                         current_status=status_filter,
                         counts=counts)


@bp.route('/memberships/archive', methods=['POST'])
@login_required
@super_admin_required
def archive_memberships():
    """Bulk archive selected memberships"""
    membership_ids = request.form.getlist('membership_ids')
    
    if not membership_ids:
        flash('No memberships selected.', 'error')
        return redirect(url_for('admin.memberships'))
    
    count = 0
    for mid in membership_ids:
        membership = Membership.query.get(int(mid))
        if membership and not membership.is_archived:
            membership.is_archived = True
            count += 1
    
    db.session.commit()
    ActionLog.log(
        action='archive_memberships',
        area='memberships',
        details={'count': count, 'membership_ids': [int(mid) for mid in membership_ids]}
    )
    flash(f'{count} membership(s) archived successfully.', 'success')
    return redirect(url_for('admin.memberships'))


@bp.route('/memberships/unarchive', methods=['POST'])
@login_required
@super_admin_required
def unarchive_memberships():
    """Bulk unarchive selected memberships"""
    membership_ids = request.form.getlist('membership_ids')
    
    if not membership_ids:
        flash('No memberships selected.', 'error')
        return redirect(url_for('admin.memberships', status='archived'))
    
    count = 0
    for mid in membership_ids:
        membership = Membership.query.get(int(mid))
        if membership and membership.is_archived:
            membership.is_archived = False
            count += 1
    
    db.session.commit()
    ActionLog.log(
        action='unarchive_memberships',
        area='memberships',
        details={'count': count, 'membership_ids': [int(mid) for mid in membership_ids]}
    )
    flash(f'{count} membership(s) restored successfully.', 'success')
    return redirect(url_for('admin.memberships'))


@bp.route('/memberships/<int:membership_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_membership(membership_id):
    """Delete a membership signup"""
    membership = Membership.query.get_or_404(membership_id)
    member_email = membership.email
    member_name = membership.full_name
    db.session.delete(membership)
    db.session.commit()
    ActionLog.log(
        action='delete_membership',
        area='memberships',
        details={'membership_id': membership_id, 'email': member_email, 'name': member_name}
    )
    flash('Membership deleted.', 'success')
    return redirect(url_for('admin.memberships'))


@bp.route('/memberships/<int:membership_id>/approve', methods=['POST'])
@login_required
@super_admin_required
def archive_single_membership(membership_id):
    """Approve a single membership (mark as archived)"""
    membership = Membership.query.get_or_404(membership_id)
    membership.is_archived = True
    db.session.commit()
    ActionLog.log(
        action='approve_membership',
        area='memberships',
        details={'membership_id': membership_id, 'email': membership.email, 'name': membership.full_name}
    )
    flash(f'{membership.full_name} approved successfully.', 'success')
    return redirect(url_for('admin.memberships'))


@bp.route('/memberships/<int:membership_id>/pending', methods=['POST'])
@login_required
@super_admin_required
def unarchive_single_membership(membership_id):
    """Move a single membership back to pending"""
    membership = Membership.query.get_or_404(membership_id)
    membership.is_archived = False
    db.session.commit()
    ActionLog.log(
        action='pending_membership',
        area='memberships',
        details={'membership_id': membership_id, 'email': membership.email, 'name': membership.full_name}
    )
    flash(f'{membership.full_name} moved to pending.', 'success')
    return redirect(url_for('admin.memberships'))


@bp.route('/memberships/download-csv', methods=['POST'])
@login_required
@super_admin_required
def download_memberships_csv():
    """Download selected memberships as CSV and auto-approve them"""
    import csv
    import io
    from flask import make_response
    
    membership_ids = request.form.getlist('membership_ids')
    
    if not membership_ids:
        flash('No memberships selected.', 'error')
        return redirect(url_for('admin.memberships'))
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # No header row - just the data as requested
    count = 0
    for mid in membership_ids:
        membership = Membership.query.get(int(mid))
        if membership:
            # Write row: lastname, firstname, email, affiliation
            writer.writerow([
                membership.last_name,
                membership.first_name,
                membership.email,
                'VIT Chennai Student'
            ])
            # Auto-approve the membership
            if not membership.is_archived:
                membership.is_archived = True
                count += 1
    
    db.session.commit()
    
    ActionLog.log(
        action='download_memberships',
        area='memberships',
        details={'downloaded_count': len(membership_ids), 'auto_approved_count': count}
    )
    
    # Create response with CSV file
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=acm_memberships.csv'
    
    return response


# ============ STUDENTS MANAGEMENT ============

@bp.route('/students/delete/<int:student_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_student(student_id):
    """Delete a student and all related data"""
    student = Student.query.get_or_404(student_id)
    
    student_email = student.email
    student_name = student.name or student_email
    google_id = student.google_id
    
    try:
        # Get all applications for this student
        applications = Application.query.filter_by(student_id=student_id).all()
        app_ids = [app.id for app in applications]
        
        # Delete round candidates for these applications
        if app_ids:
            RoundCandidate.query.filter(RoundCandidate.application_id.in_(app_ids)).delete(synchronize_session=False)
        
        # Delete question responses for these applications
        if app_ids:
            QuestionResponse.query.filter(QuestionResponse.application_id.in_(app_ids)).delete(synchronize_session=False)
        
        # Delete applications (cascade should handle this, but being explicit)
        Application.query.filter_by(student_id=student_id).delete(synchronize_session=False)
        
        # Delete Firebase user if exists
        if google_id:
            try:
                import firebase_admin
                from firebase_admin import auth as firebase_auth
                # Find user by email instead of google_id (more reliable)
                try:
                    firebase_user = firebase_auth.get_user_by_email(student_email)
                    firebase_auth.delete_user(firebase_user.uid)
                    current_app.logger.info(f'Deleted Firebase user: {student_email}')
                except firebase_admin.exceptions.NotFoundError:
                    current_app.logger.info(f'Firebase user not found: {student_email}')
            except Exception as e:
                current_app.logger.warning(f'Could not delete Firebase user: {str(e)}')
        
        # Delete the student
        db.session.delete(student)
        db.session.commit()
        
        # Log the action
        ActionLog.log(
            action='delete_student',
            area='students',
            details={
                'student_id': student_id,
                'student_email': student_email,
                'student_name': student_name
            }
        )
        
        flash(f'Student "{student_name}" and all related data deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting student: {str(e)}')
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('admin.students'))


# ============ ACTION LOGS ============

@bp.route('/logs')
@login_required
@super_admin_required
def logs():
    """View action logs with filters"""
    # Get filter parameters
    area_filter = request.args.get('area', '')
    user_filter = request.args.get('user', '')
    action_filter = request.args.get('action', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Build query
    query = ActionLog.query
    
    if area_filter:
        query = query.filter(ActionLog.area == area_filter)
    if user_filter:
        query = query.filter(ActionLog.user_email.ilike(f'%{user_filter}%'))
    if action_filter:
        query = query.filter(ActionLog.action == action_filter)
    
    # Order by newest first and paginate
    logs_pagination = query.order_by(ActionLog.timestamp.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get unique areas and actions for filter dropdowns
    areas = db.session.query(ActionLog.area).distinct().all()
    areas = [a[0] for a in areas if a[0]]
    
    actions = db.session.query(ActionLog.action).distinct().all()
    actions = [a[0] for a in actions if a[0]]
    
    return render_template('admin/logs.html',
                         logs=logs_pagination.items,
                         pagination=logs_pagination,
                         areas=areas,
                         actions=actions,
                         current_area=area_filter,
                         current_user_filter=user_filter,
                         current_action=action_filter)

