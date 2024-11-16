import os
from flask import Flask
from app import app

# For ASGI apps, you would usually wrap the app with a framework like 'Flask-SocketIO' or 'Quart' for async support.
# Since your app is synchronous, using ASGI with Flask would require additional configuration to handle async calls.

if __name__ == "__main__":
    app.run()
