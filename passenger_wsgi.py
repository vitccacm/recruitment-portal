import sys
import os

# Add the project directory to the system path
INTERP = os.path.expanduser("~/virtualenv/recruitment-portal/3.7/bin/python")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

application = create_app()
