# This file would contain the Flask app initialization code.
# It is where we create and configure the Flask application object
from flask import Flask, jsonify
from flask_cors import CORS
from .config import Config
from .shared import cache

redis_client = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize cache
    cache.init_app(app)

    # Global cors configuration
    CORS(app, resources={
        r"/process_servers/*": {"origins": ["http://localhost:3000"]},
        r"/establish_session": {"origins": ["http://localhost:3000"]},
    })

    # Import views to ensure routes are registered
    from . import views
    app.register_blueprint(views.bp)
    
    return app