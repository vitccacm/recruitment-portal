from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from authlib.integrations.flask_client import OAuth
from . import bp
from ..models import db, Student, SiteSettings

oauth = OAuth()


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


@bp.route('/google')
def google_login():
    """Initiate Google OAuth"""
    auth_settings = get_auth_settings()
    
    if not auth_settings['allow_google']:
        flash('Google sign-in is disabled.', 'error')
        return redirect(url_for('auth.login'))
    
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Failed to get user info from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        # Check if student exists by google_id or email
        student = Student.query.filter_by(google_id=user_info['sub']).first()
        
        if not student:
            # Check if email exists (could be an email-registered user)
            student = Student.query.filter_by(email=user_info['email']).first()
            if student:
                # Link Google account to existing email account
                student.google_id = user_info['sub']
                if user_info.get('picture'):
                    student.profile_picture = user_info.get('picture')
                db.session.commit()
            else:
                # Check if signups are allowed
                auth_settings = get_auth_settings()
                if not auth_settings['allow_signup']:
                    flash('New registrations are disabled.', 'error')
                    return redirect(url_for('auth.login'))
                
                # Check email domain
                if not is_email_domain_allowed(user_info['email']):
                    flash('Registration is only allowed for specific email domains.', 'error')
                    return redirect(url_for('auth.login'))
                
                # Create new student
                student = Student(
                    google_id=user_info['sub'],
                    email=user_info['email'],
                    name=user_info.get('name'),
                    profile_picture=user_info.get('picture'),
                    is_verified=True
                )
                db.session.add(student)
                db.session.commit()
                flash('Welcome to ACM Recruitment Portal!', 'success')
        else:
            # Update profile picture if changed
            if user_info.get('picture') and student.profile_picture != user_info.get('picture'):
                student.profile_picture = user_info.get('picture')
                db.session.commit()
        
        login_user(student)
        
        # Check if profile is incomplete
        if student.profile_completion < 75:
            flash('Please complete your profile to apply for departments.', 'info')
            return redirect(url_for('student.profile'))
        
        return redirect(url_for('student.dashboard'))
        
    except Exception as e:
        current_app.logger.error(f'Google OAuth error: {e}')
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))


@bp.route('/logout')
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
