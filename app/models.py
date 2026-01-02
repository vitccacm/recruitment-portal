from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    """Admin user for managing the portal"""
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='admin')  # 'admin' or 'dept-admin'
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship - department for dept-admins
    department = db.relationship('Department', backref='dept_admins', foreign_keys=[department_id])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return f"admin_{self.id}"
    
    @property
    def is_super_admin(self):
        """Check if user is a super admin"""
        return self.role == 'admin'
    
    @property
    def is_dept_admin(self):
        """Check if user is a department admin"""
        return self.role == 'dept-admin'


class Student(UserMixin, db.Model):
    """Student user authenticated via Google OAuth or Email/Password"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=True)  # Optional for email auth
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # For email/password auth
    name = db.Column(db.String(100))
    reg_no = db.Column(db.String(20))
    batch = db.Column(db.String(10))
    phone = db.Column(db.String(15))
    branch = db.Column(db.String(50))
    profile_picture = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)  # Email verification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('Application', backref='student', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return f"student_{self.id}"
    
    @property
    def profile_completion(self):
        """Calculate profile completion percentage"""
        fields = ['name', 'reg_no', 'batch', 'phone', 'branch']
        completed = sum(1 for field in fields if getattr(self, field))
        return int((completed / len(fields)) * 100)
    
    @property
    def can_apply(self):
        """Check if profile is at least 75% complete"""
        return self.profile_completion >= 75
    
    @property
    def is_email_user(self):
        """Check if user registered via email/password"""
        return self.google_id is None and self.password_hash is not None


class SiteSettings(db.Model):
    """Global site settings including auth configuration"""
    __tablename__ = 'site_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(500))
    
    @staticmethod
    def get(key, default=None):
        """Get a setting value"""
        setting = SiteSettings.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @staticmethod
    def set(key, value):
        """Set a setting value"""
        setting = SiteSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = SiteSettings(key=key, value=str(value))
            db.session.add(setting)
        db.session.commit()
    
    @staticmethod
    def get_bool(key, default=False):
        """Get a boolean setting"""
        val = SiteSettings.get(key)
        if val is None:
            return default
        return val.lower() in ('true', '1', 'yes')


class Department(db.Model):
    """Department that students can apply to"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    short_description = db.Column(db.String(200))
    image_path = db.Column(db.String(200))
    positions = db.Column(db.String(500))  # Comma-separated positions available
    requirements = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    recruitment_start = db.Column(db.DateTime)
    recruitment_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    applications = db.relationship('Application', backref='department', lazy='dynamic')
    
    @property
    def recruitment_status(self):
        """Get current recruitment status"""
        now = datetime.utcnow()
        if self.recruitment_start and now < self.recruitment_start:
            return 'upcoming'
        elif self.recruitment_end and now > self.recruitment_end:
            return 'ended'
        elif self.is_active:
            return 'open'
        return 'closed'
    
    @property
    def is_accepting_applications(self):
        """Check if department is currently accepting applications"""
        return self.recruitment_status == 'open'


class Application(db.Model):
    """Student application to a department"""
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    position = db.Column(db.String(100))
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint - one application per student per department
    __table_args__ = (
        db.UniqueConstraint('student_id', 'department_id', name='unique_student_department'),
    )


class Round(db.Model):
    """Recruitment round (global, applies to all departments)"""
    __tablename__ = 'rounds'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    prerequisite_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=True)
    is_visible_before_results = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship for prerequisite
    prerequisite = db.relationship('Round', remote_side=[id], backref='dependent_rounds')
    
    # Relationships
    department_states = db.relationship('RoundDepartment', backref='round', lazy='dynamic', cascade='all, delete-orphan')
    candidates = db.relationship('RoundCandidate', backref='round', lazy='dynamic', cascade='all, delete-orphan')


class RoundDepartment(db.Model):
    """Per-department state for a round"""
    __tablename__ = 'round_departments'
    
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    is_locked = db.Column(db.Boolean, default=False)
    results_released = db.Column(db.Boolean, default=False)
    notes_public = db.Column(db.Boolean, default=False)
    
    # Relationship
    department = db.relationship('Department', backref='round_states')
    
    __table_args__ = (
        db.UniqueConstraint('round_id', 'department_id', name='unique_round_department'),
    )


class RoundCandidate(db.Model):
    """Candidate status in a round"""
    __tablename__ = 'round_candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('rounds.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, selected, not_selected
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    application = db.relationship('Application', backref='round_entries')
    
    __table_args__ = (
        db.UniqueConstraint('round_id', 'application_id', name='unique_round_application'),
    )
    
    @property
    def department_id(self):
        """Get department ID from application"""
        return self.application.department_id if self.application else None


class DepartmentQuestion(db.Model):
    """Custom question for department applications"""
    __tablename__ = 'department_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # text, single_choice, multiple_choice, file_upload, link
    options = db.Column(db.Text)  # JSON for choices
    is_required = db.Column(db.Boolean, default=False)
    file_max_size = db.Column(db.Integer, default=1024)  # KB, for file uploads
    allowed_extensions = db.Column(db.String(100), default='pdf')  # comma-separated
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    department = db.relationship('Department', backref='custom_questions')
    responses = db.relationship('QuestionResponse', backref='question', cascade='all, delete-orphan')


class QuestionResponse(db.Model):
    """Response to a custom department question"""
    __tablename__ = 'question_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('department_questions.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    response_text = db.Column(db.Text)
    file_path = db.Column(db.String(255))  # For file uploads
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    application = db.relationship('Application', backref='question_responses')
    
    __table_args__ = (
        db.UniqueConstraint('question_id', 'application_id', name='unique_question_response'),
    )


class ProfileField(db.Model):
    """Customizable profile field for students"""
    __tablename__ = 'profile_fields'
    
    id = db.Column(db.Integer, primary_key=True)
    field_name = db.Column(db.String(50), nullable=False)  # internal name
    label = db.Column(db.String(100), nullable=False)  # display label
    field_type = db.Column(db.String(20), default='text')  # text, select, number
    options = db.Column(db.Text)  # JSON for select options
    is_required = db.Column(db.Boolean, default=False)
    is_enabled = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
