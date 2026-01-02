from flask import Blueprint

bp = Blueprint('dept', __name__)

from . import routes
