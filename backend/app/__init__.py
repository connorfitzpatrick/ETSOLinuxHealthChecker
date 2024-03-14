# This file would contain the Flask app initialization code.
# It is where we create and configure the Flask application object
# __init__.py
from flask import Flask, current_app, jsonify
from flask_cors import CORS
from threading import Thread
# from celery import Celery
from .config import Config
import redis


redis_client = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/process_servers/*": {"origins": ["http://localhost:3000"]}})

    # Import views to ensure routes are registered
    from . import views
    app.register_blueprint(views.bp)
    
    @app.route('/test_async', methods=['GET'])
    async def test_async():
        x = await test_async1()
        return x

    async def test_async1():
        return jsonify({'message': 'Async route works'}), 200

    return app