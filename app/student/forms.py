from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Length, Regexp


BRANCH_CHOICES = [
    ('', 'Select Branch'),
    ('CSE', 'B.Tech CSE CORE'),
    ('CSE-AIML', 'B.Tech CSE AIML'),
    ('CSE-AIR', 'B.Tech CSE AIRobotics'),
    ('CSE-DS', 'B.Tech CSE Data Science'),
    ('CSE-CS', 'B.Tech CSE CyberSec'),
    ('MECH', 'B.Tech MECH'),
    ('MECH-AUTO', 'B.Tech Mechatronics'),
    ('CIVIL', 'B.Tech Civil'),
    ('ECE', 'B.Tech Electronics and Communication'),
    ('ECE-COMP', 'B.Tech Electronics and Computer'),
    ('ECE-VLSI', 'B.Tech Electronics Engineering (VLSI Design and Technology)'),
    ('FT', 'B.Tech Fashion Technology'),
    ('EEE', 'B.Tech. Electrical and Electronics Engineering'),
    ('ECS', 'B.Tech. Electrical and Computer Science Engineering'),
]

BATCH_CHOICES = [
    ('', 'Select Batch'),
    ('2024', '2024'),
    ('2025', '2025'),
    ('2026', '2026'),
    ('2027', '2027'),
    ('2028', '2028'),
]


class ProfileForm(FlaskForm):
    """Form for student profile completion"""
    first_name = StringField('First Name', validators=[
        DataRequired(message='First name is required'),
        Length(min=1, max=50, message='First name must be between 1 and 50 characters')
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(message='Last name is required'),
        Length(min=1, max=50, message='Last name must be between 1 and 50 characters')
    ])
    reg_no = StringField('Registration Number', validators=[
        DataRequired(message='Registration number is required'),
        Length(min=5, max=20, message='Invalid registration number')
    ])
    batch = SelectField('Batch (Year of Joining)', choices=BATCH_CHOICES, validators=[
        DataRequired(message='Please select your batch')
    ])
    phone = StringField('Phone Number', validators=[
        DataRequired(message='Phone number is required'),
        Regexp(r'^\+?[0-9]{10,15}$', message='Please enter a valid phone number')
    ])
    branch = SelectField('Branch', choices=BRANCH_CHOICES, validators=[
        DataRequired(message='Please select your branch')
    ])


class ApplicationForm(FlaskForm):
    """Form for applying to a department"""
    position = SelectField('Position', validators=[DataRequired(message='Please select a position')])
    cover_letter = TextAreaField('Why do you want to join? (Optional)', validators=[
        Length(max=2000, message='Cover letter must be under 2000 characters')
    ])
