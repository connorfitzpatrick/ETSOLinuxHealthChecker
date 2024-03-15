# This file would contain the Flask app initialization code.
# It is where we create and configure the Flask application object
# __init__.py
from flask import Flask, current_app, jsonify
from flask_cors import CORS
from threading import Thread
# from celery import Celery
from .config import Config
# import redis
# from flask_caching import Cache
from .shared import cache


redis_client = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Setup cache
    # app.config['CACHE_TYPE'] = 'SimpleCache'
    # app.config['CACHE_DEFAULT_TIMEOUT'] = 300
    # cache = Cache(app)
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