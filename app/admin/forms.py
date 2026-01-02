from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField, BooleanField, DateTimeLocalField, SelectField, IntegerField
from wtforms.validators import DataRequired, Length, Optional


class LoginForm(FlaskForm):
    """Admin login form"""
    email = StringField('Email/Username', validators=[
        DataRequired(message='Email is required')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])


class DepartmentCreateForm(FlaskForm):
    """Quick create department with name only"""
    name = StringField('Department Name', validators=[
        DataRequired(message='Department name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])


class DepartmentEditForm(FlaskForm):
    """Full department edit form"""
    name = StringField('Department Name', validators=[
        DataRequired(message='Department name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    short_description = StringField('Short Description', validators=[
        Optional(),
        Length(max=200, message='Short description must be under 200 characters')
    ])
    description = TextAreaField('Full Description', validators=[
        Optional(),
        Length(max=5000, message='Description must be under 5000 characters')
    ])
    positions = StringField('Positions (comma-separated)', validators=[
        Optional(),
        Length(max=500, message='Positions must be under 500 characters')
    ])
    requirements = TextAreaField('Requirements', validators=[
        Optional(),
        Length(max=2000, message='Requirements must be under 2000 characters')
    ])
    image = FileField('Department Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only!')
    ])
    recruitment_start = DateTimeLocalField('Recruitment Start', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    recruitment_end = DateTimeLocalField('Recruitment End', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    is_active = BooleanField('Active')


class ApplicationStatusForm(FlaskForm):
    """Form to update application status"""
    pass  # Just for CSRF protection


class AccountForm(FlaskForm):
    """Form for creating admin accounts"""
    name = StringField('Name', validators=[
        DataRequired(message='Name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    email = StringField('Email/Username', validators=[
        DataRequired(message='Email is required'),
        Length(min=2, max=120, message='Email must be between 2 and 120 characters')
    ])
    role = StringField('Role')  # Will be set via select in template
    department_id = StringField('Department')  # For dept-admin
    password = PasswordField('Password', validators=[
        Optional(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    generate_password = BooleanField('Generate Random Password')


class RoundForm(FlaskForm):
    """Form for creating/editing rounds"""
    name = StringField('Round Name', validators=[
        DataRequired(message='Round name is required'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=2000, message='Description must be under 2000 characters')
    ])
    prerequisite_id = SelectField('Prerequisite Round', coerce=int, validators=[Optional()])
    is_visible_before_results = BooleanField('Show to applicants before results are released')
    order = IntegerField('Display Order', default=0)
