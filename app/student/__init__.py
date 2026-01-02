from flask import Blueprint

bp = Blueprint('student', __name__)

from . import routes
