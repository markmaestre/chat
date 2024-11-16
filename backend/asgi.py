import os
from app import app

os.environ.setdefault('FLASK_ENV', 'production')

# ASGI callable
application = app
