from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.utils import secure_filename
import os
from . import bp
from .forms import ProfileForm, ApplicationForm
from ..models import db, Student, Department, Application, Round, RoundDepartment, RoundCandidate, DepartmentQuestion, QuestionResponse


def student_required(f):
    """Decorator to ensure user is a student"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(current_user, 'google_id'):
            flash('Access denied. Students only.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def profile_complete_required(f):
    """Decorator to ensure profile is at least 75% complete"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.can_apply:
            flash('Please complete at least 75% of your profile to continue.', 'warning')
            return redirect(url_for('student.profile'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student dashboard"""
    recent_applications = current_user.applications.order_by(Application.applied_at.desc()).limit(5).all()
    open_departments = Department.query.filter_by(is_active=True).count()
    return render_template('student/dashboard.html', 
                         recent_applications=recent_applications,
                         open_departments=open_departments)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
@student_required
def profile():
    """View and edit profile"""
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.reg_no = form.reg_no.data
        current_user.batch = form.batch.data
        current_user.phone = form.phone.data
        current_user.branch = form.branch.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.dashboard'))
    
    return render_template('student/profile.html', form=form)


@bp.route('/departments')
@login_required
@student_required
def departments():
    """View all departments"""
    departments = Department.query.filter_by(is_active=True).order_by(Department.created_at.desc()).all()
    
    # Get departments user has already applied to
    applied_dept_ids = [app.department_id for app in current_user.applications.all()]
    
    return render_template('student/departments.html', 
                         departments=departments,
                         applied_dept_ids=applied_dept_ids)


@bp.route('/department/<int:dept_id>')
@login_required
@student_required
def department_detail(dept_id):
    """View department details"""
    department = Department.query.get_or_404(dept_id)
    existing_application = Application.query.filter_by(
        student_id=current_user.id,
        department_id=dept_id
    ).first()
    return render_template('student/department_detail.html', 
                         department=department,
                         existing_application=existing_application)


@bp.route('/apply/<int:dept_id>', methods=['GET', 'POST'])
@login_required
@student_required
@profile_complete_required
def apply(dept_id):
    """Apply to a department"""
    department = Department.query.get_or_404(dept_id)
    
    # Check if already applied
    existing = Application.query.filter_by(
        student_id=current_user.id,
        department_id=dept_id
    ).first()
    
    if existing:
        flash('You have already applied to this department.', 'warning')
        return redirect(url_for('student.applications'))
    
    # Check if department is accepting applications
    if not department.is_accepting_applications:
        flash('This department is not currently accepting applications.', 'error')
        return redirect(url_for('student.department_detail', dept_id=dept_id))
    
    # Get available positions
    positions = []
    if department.positions:
        positions = [(p.strip(), p.strip()) for p in department.positions.split(',')]
    
    # Get custom questions for this department
    questions = DepartmentQuestion.query.filter_by(department_id=dept_id).order_by(DepartmentQuestion.order).all()
    
    form = ApplicationForm()
    form.position.choices = [('', 'Select Position')] + positions
    
    if request.method == 'POST':
        # Validate required questions
        missing_required = []
        for q in questions:
            if q.is_required:
                if q.question_type == 'file_upload':
                    if f'question_{q.id}' not in request.files or not request.files[f'question_{q.id}'].filename:
                        missing_required.append(q.question_text[:40])
                else:
                    if not request.form.get(f'question_{q.id}'):
                        missing_required.append(q.question_text[:40])
        
        if missing_required:
            flash(f'Please answer required questions: {", ".join(missing_required)}', 'error')
        elif form.validate():
            # Create application
            application = Application(
                student_id=current_user.id,
                department_id=dept_id,
                position=form.position.data,
                cover_letter=form.cover_letter.data
            )
            db.session.add(application)
            db.session.flush()  # Get application ID
            
            # Save question responses
            for q in questions:
                response_text = None
                file_path = None
                
                if q.question_type == 'file_upload':
                    if f'question_{q.id}' in request.files:
                        file = request.files[f'question_{q.id}']
                        if file and file.filename:
                            filename = secure_filename(f"app{application.id}_q{q.id}_{file.filename}")
                            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                            file.save(filepath)
                            file_path = f"uploads/{filename}"
                elif q.question_type == 'multiple_choice':
                    choices = request.form.getlist(f'question_{q.id}')
                    response_text = ','.join(choices) if choices else None
                else:
                    response_text = request.form.get(f'question_{q.id}')
                
                if response_text or file_path:
                    qr = QuestionResponse(
                        question_id=q.id,
                        application_id=application.id,
                        response_text=response_text,
                        file_path=file_path
                    )
                    db.session.add(qr)
            
            db.session.commit()
            flash(f'Application submitted to {department.name}!', 'success')
            return redirect(url_for('student.applications'))
    
    return render_template('student/apply.html', form=form, department=department, questions=questions)


@bp.route('/applications')
@login_required
@student_required
def applications():
    """View my applications"""
    applications = current_user.applications.order_by(Application.applied_at.desc()).all()
    return render_template('student/applications.html', applications=applications)


@bp.route('/rounds')
@login_required
@student_required
def rounds():
    """View rounds status for all my applications"""
    # Get all user's applications
    user_apps = current_user.applications.all()
    
    # Build rounds data per application
    rounds_by_dept = {}
    
    for app in user_apps:
        dept_id = app.department_id
        dept_name = app.department.name
        
        # Get all rounds for this department
        dept_rounds = []
        all_rounds = Round.query.order_by(Round.order).all()
        
        for r in all_rounds:
            rd = RoundDepartment.query.filter_by(round_id=r.id, department_id=dept_id).first()
            if not rd:
                continue
            
            # Check if round is visible to user
            if not r.is_visible_before_results and not rd.results_released:
                continue
            
            # Get candidate entry
            rc = RoundCandidate.query.filter_by(round_id=r.id, application_id=app.id).first()
            
            # Check eligibility (if has prerequisite, must have passed it)
            is_eligible = True
            if r.prerequisite_id:
                prereq_rc = RoundCandidate.query.filter_by(
                    round_id=r.prerequisite_id,
                    application_id=app.id,
                    status='selected'
                ).first()
                is_eligible = prereq_rc is not None
            
            dept_rounds.append({
                'round': r,
                'state': rd,
                'candidate': rc,
                'is_eligible': is_eligible,
            })
        
        if dept_rounds:
            rounds_by_dept[dept_name] = {
                'application': app,
                'rounds': dept_rounds
            }
    
    return render_template('student/rounds.html', rounds_by_dept=rounds_by_dept)
