import sys
import os

# Insert project directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Import the application factory
from app import create_app
from app.config import Config

# Create the application instance
# cPanel Phusion Passenger looks for 'application' object
application = create_app(Config)
