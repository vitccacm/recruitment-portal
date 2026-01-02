import os
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
from . import bp
from ..admin.forms import DepartmentEditForm
from ..models import db, Admin, Department, Application, Round, RoundDepartment, RoundCandidate, DepartmentQuestion


def dept_admin_required(f):
    """Decorator to ensure user is a dept-admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not isinstance(current_user, Admin):
            flash('Access denied.', 'error')
            return redirect(url_for('admin.login'))
        if not current_user.is_dept_admin:
            flash('Access denied. Dept admin only.', 'error')
            return redirect(url_for('admin.dashboard'))
        if not current_user.department_id:
            flash('No department assigned. Contact super admin.', 'error')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@dept_admin_required
def dashboard():
    """Dept admin dashboard"""
    department = Department.query.get(current_user.department_id)
    if not department:
        flash('Department not found.', 'error')
        return redirect(url_for('admin.login'))
    
    stats = {
        'total_applications': department.applications.count(),
        'pending_applications': department.applications.filter_by(status='pending').count(),
        'accepted_applications': department.applications.filter_by(status='accepted').count(),
        'rejected_applications': department.applications.filter_by(status='rejected').count(),
    }
    recent_applications = department.applications.order_by(Application.applied_at.desc()).limit(10).all()
    
    return render_template('dept/dashboard.html', 
                         department=department, 
                         stats=stats, 
                         recent_applications=recent_applications)


@bp.route('/applications')
@login_required
@dept_admin_required
def applications():
    """View department applications"""
    department = Department.query.get(current_user.department_id)
    status_filter = request.args.get('status', '')
    
    query = department.applications
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    applications = query.order_by(Application.applied_at.desc()).all()
    
    return render_template('dept/applications.html', 
                         department=department,
                         applications=applications,
                         current_status=status_filter)


@bp.route('/department')
@login_required
@dept_admin_required
def view_department():
    """View department details"""
    department = Department.query.get(current_user.department_id)
    if not department:
        flash('Department not found.', 'error')
        return redirect(url_for('admin.login'))
    
    return render_template('dept/department.html', department=department)


@bp.route('/department/edit', methods=['GET', 'POST'])
@login_required
@dept_admin_required
def edit_department():
    """Edit department details"""
    department = Department.query.get(current_user.department_id)
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
        return redirect(url_for('dept.view_department'))
    
    return render_template('dept/edit.html', form=form, department=department)


# ============ ROUNDS MANAGEMENT ============

@bp.route('/rounds')
@login_required
@dept_admin_required
def rounds():
    """List rounds for this department"""
    dept_id = current_user.department_id
    
    # Get all rounds with their department states
    rounds_data = []
    all_rounds = Round.query.order_by(Round.order).all()
    
    for r in all_rounds:
        rd = RoundDepartment.query.filter_by(round_id=r.id, department_id=dept_id).first()
        if rd:
            candidates = RoundCandidate.query.join(Application).filter(
                RoundCandidate.round_id == r.id,
                Application.department_id == dept_id
            ).all()
            
            rounds_data.append({
                'round': r,
                'state': rd,
                'total': len(candidates),
                'selected': len([c for c in candidates if c.status == 'selected']),
            })
    
    return render_template('dept/rounds.html', rounds_data=rounds_data)


@bp.route('/rounds/<int:round_id>')
@login_required
@dept_admin_required
def round_detail(round_id):
    """View round candidates for this department"""
    dept_id = current_user.department_id
    round_obj = Round.query.get_or_404(round_id)
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    
    # Get eligible applications
    if round_obj.prerequisite_id:
        # Only applications that passed the prerequisite
        eligible_apps = []
        dept_apps = Application.query.filter_by(department_id=dept_id).all()
        for app in dept_apps:
            prereq_candidate = RoundCandidate.query.filter_by(
                round_id=round_obj.prerequisite_id,
                application_id=app.id,
                status='selected'
            ).first()
            if prereq_candidate:
                eligible_apps.append(app)
    else:
        # All department applications
        eligible_apps = Application.query.filter_by(department_id=dept_id).all()
    
    # Get current round candidates
    candidates = {}
    for rc in RoundCandidate.query.filter_by(round_id=round_id).all():
        if rc.application.department_id == dept_id:
            candidates[rc.application_id] = rc
    
    return render_template('dept/round_candidates.html', 
                         round=round_obj,
                         state=rd,
                         eligible_apps=eligible_apps,
                         candidates=candidates)


@bp.route('/rounds/<int:round_id>/toggle/<int:app_id>', methods=['POST'])
@login_required
@dept_admin_required
def toggle_candidate(round_id, app_id):
    """Toggle candidate selection for a round"""
    dept_id = current_user.department_id
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    
    # Check if locked
    if rd.is_locked:
        flash('Round is locked. Cannot modify.', 'error')
        return redirect(url_for('dept.round_detail', round_id=round_id))
    
    # Verify application belongs to this department
    app = Application.query.get_or_404(app_id)
    if app.department_id != dept_id:
        flash('Access denied.', 'error')
        return redirect(url_for('dept.round_detail', round_id=round_id))
    
    # Get or create candidate entry
    rc = RoundCandidate.query.filter_by(round_id=round_id, application_id=app_id).first()
    
    if rc:
        # Toggle status
        if rc.status == 'selected':
            rc.status = 'not_selected'
        else:
            rc.status = 'selected'
    else:
        # Create new entry as selected
        rc = RoundCandidate(round_id=round_id, application_id=app_id, status='selected')
        db.session.add(rc)
    
    db.session.commit()
    return redirect(url_for('dept.round_detail', round_id=round_id))


@bp.route('/rounds/<int:round_id>/notes/<int:app_id>', methods=['POST'])
@login_required
@dept_admin_required
def update_notes(round_id, app_id):
    """Update candidate notes"""
    dept_id = current_user.department_id
    rd = RoundDepartment.query.filter_by(round_id=round_id, department_id=dept_id).first_or_404()
    
    if rd.is_locked:
        flash('Round is locked.', 'error')
        return redirect(url_for('dept.round_detail', round_id=round_id))
    
    app = Application.query.get_or_404(app_id)
    if app.department_id != dept_id:
        flash('Access denied.', 'error')
        return redirect(url_for('dept.round_detail', round_id=round_id))
    
    rc = RoundCandidate.query.filter_by(round_id=round_id, application_id=app_id).first()
    if not rc:
        rc = RoundCandidate(round_id=round_id, application_id=app_id, status='pending')
        db.session.add(rc)
    
    rc.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Notes updated.', 'success')
    return redirect(url_for('dept.round_detail', round_id=round_id))


# ============ CUSTOM QUESTIONS ============

@bp.route('/questions')
@login_required
@dept_admin_required
def questions():
    """Manage custom application questions"""
    dept_id = current_user.department_id
    questions = DepartmentQuestion.query.filter_by(department_id=dept_id).order_by(DepartmentQuestion.order).all()
    return render_template('dept/questions.html', questions=questions)


@bp.route('/questions/add', methods=['GET', 'POST'])
@login_required
@dept_admin_required
def add_question():
    """Add a new application question"""
    if request.method == 'POST':
        q = DepartmentQuestion(
            department_id=current_user.department_id,
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
        return redirect(url_for('dept.questions'))
    
    return render_template('dept/question_form.html', question=None)


@bp.route('/questions/<int:q_id>/edit', methods=['GET', 'POST'])
@login_required
@dept_admin_required
def edit_question(q_id):
    """Edit a question"""
    q = DepartmentQuestion.query.get_or_404(q_id)
    if q.department_id != current_user.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('dept.questions'))
    
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
        return redirect(url_for('dept.questions'))
    
    return render_template('dept/question_form.html', question=q)


@bp.route('/questions/<int:q_id>/delete', methods=['POST'])
@login_required
@dept_admin_required
def delete_question(q_id):
    """Delete a question"""
    q = DepartmentQuestion.query.get_or_404(q_id)
    if q.department_id != current_user.department_id:
        flash('Access denied.', 'error')
        return redirect(url_for('dept.questions'))
    
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted.', 'success')
    return redirect(url_for('dept.questions'))
