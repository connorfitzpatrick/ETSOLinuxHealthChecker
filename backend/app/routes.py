# This file contains route definitions

from flask import request, jsonify, Response
from flask_cors import cross_origin
from .views import process_servers
from app import app

# @app.route('/process_servers/', methods=['POST', 'GET'])
# @cross_origin(origin='http://localhost:3000')
# def process_servers_flask():
#     return process_servers(request)
