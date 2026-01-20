from flask import render_template, request, jsonify
from . import bp
from ..models import Department, Membership, db, PageVisit
from .. import csrf


@bp.route('/')
def index():
    """Landing page with department overview"""
    PageVisit.track('Homepage')
    departments = Department.query.filter_by(is_active=True).order_by(Department.created_at.desc()).all()
    return render_template('main/index.html', departments=departments)


@bp.route('/departments')
def departments():
    """View all departments (public)"""
    PageVisit.track('Departments List')
    departments = Department.query.order_by(Department.created_at.desc()).all()
    return render_template('main/departments.html', departments=departments)


@bp.route('/department/<int:dept_id>')
def department_detail(dept_id):
    """View department details (public)"""
    department = Department.query.get_or_404(dept_id)
    PageVisit.track(f'Department: {department.name}')
    return render_template('main/department_detail.html', department=department)


@bp.route('/membership')
def membership():
    """View membership information"""
    PageVisit.track('Membership Page')
    return render_template('main/membership.html')


@csrf.exempt
@bp.route('/api/membership/join', methods=['POST'])
def join_membership():
    """Handle membership signup"""
    data = request.get_json()
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    
    # Validate input
    if not email or not first_name or not last_name:
        return jsonify({'success': False, 'message': 'Email, first name, and last name are required'}), 400
    
    # Check if email already exists
    existing = Membership.query.filter_by(email=email).first()
    if existing:
        return jsonify({'success': False, 'message': 'This email is already registered for membership'}), 400
    
    try:
        # Create new membership record
        new_membership = Membership(email=email, first_name=first_name, last_name=last_name)
        db.session.add(new_membership)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Thank you for joining ACM! We will contact you soon.'
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'}), 500
