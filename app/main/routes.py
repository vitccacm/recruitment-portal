from flask import render_template
from . import bp
from ..models import Department


@bp.route('/')
def index():
    """Landing page with department overview"""
    departments = Department.query.filter_by(is_active=True).order_by(Department.created_at.desc()).all()
    return render_template('main/index.html', departments=departments)


@bp.route('/departments')
def departments():
    """View all departments (public)"""
    departments = Department.query.order_by(Department.created_at.desc()).all()
    return render_template('main/departments.html', departments=departments)


@bp.route('/department/<int:dept_id>')
def department_detail(dept_id):
    """View department details (public)"""
    department = Department.query.get_or_404(dept_id)
    return render_template('main/department_detail.html', department=department)
