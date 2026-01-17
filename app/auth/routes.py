from flask import render_template, redirect, url_for, flash, request, session, current_app, jsonify
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from authlib.integrations.flask_client import OAuth
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from . import bp
from ..models import db, Student, SiteSettings
from .. import csrf
import os
from functools import wraps

oauth = OAuth()

# Initialize Firebase Admin SDK
try:
    # Check if already initialized
    firebase_admin.get_app()
except ValueError:
    # Initialize with service account
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": "acm-recruitment-4886d",
        "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
        "private_key": os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n'),
        "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.getenv('FIREBASE_CLIENT_ID'),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": os.getenv('FIREBASE_CERT_URL')
    })
    firebase_admin.initialize_app(cred)


def init_oauth(app):
    """Initialize OAuth with the app"""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )


class RegisterForm(FlaskForm):
    """Student registration form"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])


class EmailLoginForm(FlaskForm):
    """Email login form"""
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


def get_auth_settings():
    """Get current auth settings"""
    return {
        'allow_signup': SiteSettings.get_bool('allow_signup', True),
        'allow_google': SiteSettings.get_bool('allow_google', True),
        'allow_email': SiteSettings.get_bool('allow_email', True),
        'allowed_domains': SiteSettings.get('allowed_domains', ''),
    }


def is_email_domain_allowed(email):
    """Check if email domain is allowed"""
    allowed_domains = SiteSettings.get('allowed_domains', '')
    if not allowed_domains or not allowed_domains.strip():
        return True  # No restriction if empty
    
    domains = [d.strip().lower() for d in allowed_domains.split(',') if d.strip()]
    if not domains:
        return True
    
    email_domain = email.lower().split('@')[-1]
    return email_domain in domains


@bp.route('/google-login', methods=['POST'])
@csrf.exempt
def google_login():
    """Handle Firebase Google Sign-In"""
    try:
        print("DEBUG: google_login route called")
        data = request.get_json()
        print(f"DEBUG: Request data: {data}")
        id_token = data.get('idToken') if data else None
        
        if not id_token:
            return jsonify({'success': False, 'message': 'No token provided'}), 400
        
        # Verify the Firebase ID token
        decoded_token = firebase_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name')
        picture = decoded_token.get('picture')
        
        if not email:
            return jsonify({'success': False, 'message': 'Email not provided by Google'}), 400
        
        # Check email domain restrictions
        if not is_email_domain_allowed(email):
            return jsonify({
                'success': False,
                'message': 'Registration is only allowed for specific email domains'
            }), 403
        
        # Check if student exists
        student = Student.query.filter_by(google_id=uid).first()
        
        if not student:
            # Check by email (in case of account linking)
            student = Student.query.filter_by(email=email).first()
            if student:
                # Link Google account
                student.google_id = uid
                if picture:
                    student.profile_picture = picture
            else:
                # Check if signups allowed
                auth_settings = get_auth_settings()
                if not auth_settings['allow_signup']:
                    return jsonify({
                        'success': False,
                        'message': 'New registrations are currently disabled'
                    }), 403
                
                # Create new student
                student = Student(
                    google_id=uid,
                    email=email,
                    name=name,
                    profile_picture=picture,
                    is_verified=True
                )
                db.session.add(student)
        else:
            # Update profile if changed
            if picture and student.profile_picture != picture:
                student.profile_picture = picture
            if name and student.name != name:
                student.name = name
        
        db.session.commit()
        
        # Log the user in
        login_user(student, remember=True)
        
        return jsonify({
            'success': True,
            'redirect_url': url_for('student.dashboard')
        })
        
    except firebase_auth.InvalidIdTokenError as e:
        print(f"DEBUG: InvalidIdTokenError: {str(e)}")
        current_app.logger.error(f'InvalidIdTokenError: {str(e)}')
        return jsonify({'success': False, 'message': 'Invalid authentication token'}), 401
    except firebase_auth.ExpiredIdTokenError as e:
        print(f"DEBUG: ExpiredIdTokenError: {str(e)}")
        current_app.logger.error(f'ExpiredIdTokenError: {str(e)}')
        return jsonify({'success': False, 'message': 'Authentication token expired'}), 401
    except Exception as e:
        print(f"DEBUG: Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        current_app.logger.error(f'Firebase auth error: {str(e)}')
        return jsonify({'success': False, 'message': f'Authentication failed: {str(e)}'}), 500


@bp.route('/login')
def login():
    """Show login page"""
    if current_user.is_authenticated:
        if hasattr(current_user, 'google_id') or hasattr(current_user, 'is_email_user'):
            return redirect(url_for('student.dashboard'))
        return redirect(url_for('admin.dashboard'))
    
    auth_settings = get_auth_settings()
    return render_template('auth/login.html', auth_settings=auth_settings)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """Student email registration"""
    auth_settings = get_auth_settings()
    
    if not auth_settings['allow_signup']:
        flash('New registrations are currently disabled.', 'error')
        return redirect(url_for('auth.login'))
    
    if not auth_settings['allow_email']:
        flash('Email registration is disabled. Please use Google sign-in.', 'error')
        return redirect(url_for('auth.login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('student.dashboard'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Check email domain
        if not is_email_domain_allowed(form.email.data):
            flash('Registration is only allowed for specific email domains.', 'error')
            return render_template('auth/register.html', form=form, auth_settings=auth_settings)
        
        # Check if email exists
        existing = Student.query.filter_by(email=form.email.data.lower()).first()
        if existing:
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html', form=form, auth_settings=auth_settings)
        
        # Create new student
        student = Student(
            email=form.email.data.lower(),
            is_verified=True  # Skip email verification for now
        )
        student.set_password(form.password.data)
        db.session.add(student)
        db.session.commit()
        
        login_user(student)
        flash('Account created! Please complete your profile.', 'success')
        return redirect(url_for('student.profile'))
    
    return render_template('auth/register.html', form=form, auth_settings=auth_settings)


@bp.route('/email-login', methods=['POST'])
def email_login():
    """Handle email/password login"""
    auth_settings = get_auth_settings()
    
    if not auth_settings['allow_email']:
        flash('Email login is disabled.', 'error')
        return redirect(url_for('auth.login'))
    
    form = EmailLoginForm()
    
    if form.validate_on_submit():
        student = Student.query.filter_by(email=form.email.data.lower()).first()
        
        if student and student.check_password(form.password.data):
            login_user(student)
            
            if student.profile_completion < 75:
                flash('Please complete your profile to apply for departments.', 'info')
                return redirect(url_for('student.profile'))
            
            return redirect(url_for('student.dashboard'))
        
        flash('Invalid email or password.', 'error')
    
    return redirect(url_for('auth.login'))


@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Logout user"""
    logout_user()
    if request.method == 'POST':
        return jsonify({'success': True}), 200
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
