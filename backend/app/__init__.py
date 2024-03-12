# This file would contain the Flask app initialization code.
# It is where we create and configure the Flask application object
from flask import Flask, current_app
from flask_cors import CORS
from threading import Thread
from celery import Celery
from .config import Config
from .utils.server_utils import start_kafka_consumer
import redis

redis_client = None

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # app.config['CELERY_BROKER_URL'] = 'amqp://localhost'  # or your broker URL
    # app.config['CELERY_RESULT_BACKEND'] = 'rpc'

    # celeryconfig.py
    app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
    app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
    celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)

    CORS(app, resources={r"/process_servers/*": {"origins": ["http://localhost:3000"]}})

    # Import views to ensure routes are registered
    from . import views
    app.register_blueprint(views.bp)

    return app