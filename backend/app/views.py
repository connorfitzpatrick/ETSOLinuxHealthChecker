'''
This file is in charge of defining the logic of HTTP request handlers of the app.
'''
# views.py
from flask import request, Blueprint, jsonify, Response, stream_with_context
from flask_cors import cross_origin
from .shared import cache
import json
from .utils.server_utils import process_server_health
from threading import Thread
import time
import logging
import asyncio
import tracemalloc

# Your existing view logic, adapted for Flask

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(threadName)s] %(message)s')
logger = logging.getLogger(__name__)

bp = Blueprint('bp', __name__)

# GLOBAL dictionary for maintaining the state of each connection with a unique ID 
connection_states = {}

@bp.route('/simple_async_test/', methods=['GET'])
async def simple_async_test():
    return jsonify({'message': 'Simple async test successful'}), 200

@bp.route('/establish_session', methods=['GET'])
def establish_connection():
    connection_id = request.headers.get('X-Connection-Id')
    connection_states[connection_id] = {'servers': []}
    return jsonify({'message': 'Session with Connection ID ' + connection_id + ' established'}), 200

@bp.route('/process_servers/', methods=['POST'])
async def process_servers():
    # x = await test1()
    # return jsonify({'message': x}), 200
    print("IN PROCESS_SERVERS FUNCTION")

    if request.method == 'POST':
        print("REACTING TO POST REQUEST")
        # Your processing logic here
        data = request.json
        servers = data.get('serverNames', [])
        connection_id = request.headers.get('X-Connection-Id')
        print(servers)
        
        # Initialize the state for this connection
        connection_states[connection_id] = {
            # list of servers
            'servers': servers,
            # timestamp of when health check results were obtained for each server
            'last_updates': {server: 0 for server in servers},
            # indicates if all health check results were returned to client
            'all_results_sent': False       
        }

        print(connection_states[connection_id])
        await process_server_health(servers, connection_id)

        return jsonify({'message': 'Server processing started'}), 200

@bp.route('/process_servers/', methods=['GET'])
def get_results():
    if request.method == 'GET':
        # Extract UUID from header
        connection_id = request.args.get('id')
        # Ensure connection_id was already initialized in the POST request
        if connection_id not in connection_states:
            return jsonify({'error': 'Connection not initialized'}), 400
        # Stream results to client
        return Response(stream_with_context(server_events(connection_id, connection_states)), mimetype='text/event-stream')

    else:
        return jsonify({'message': 'Error: Request could not be processed'}), 405


def server_events(connection_id, connection_states):
    start_time = time.time()
    timeout = 120  # Timeout after 120 seconds of no updates
    results_returned = 0

    while True:
        all_servers_updated = True
        print("SERVERS:")
        print(connection_states[connection_id]['servers'])
        for server in connection_states[connection_id]['servers']:
            # Retrieve the last update time for this server from the connection state
            last_update = connection_states[connection_id]['last_updates'].get(server, 0)
            # Retrieve the server update from Redis
            cache_key = connection_id + "-" + server
            server_update = cache.get(cache_key)

            if server_update:
                print("SERVER UPDATE")
                print(server_update)
                server_update = json.loads(server_update)
                if last_update < server_update['last_updated']:
                    event_data = {'server': server, 'status': server_update['status']}
                    yield f"data: {json.dumps(event_data)}\n\n"
                    connection_states[connection_id]['last_updates'][server] = server_update['last_updated']
                    results_returned += 1
            else:
                all_servers_updated = False

        if all_servers_updated and len(connection_states[connection_id]['servers']) > 0 and results_returned == len(connection_states[connection_id]['servers']):
            print("All Servers are checked. Closing session")
            break

        if time.time() - start_time > timeout:
            yield "data: {\"message\": \"Timeout reached\"}\n\n"
            break
        
        # Sleep to prevent a tight loop
        time.sleep(1.5)
    
    # Clean up by removing connection state to free resources
    if connection_id in connection_states:
        del connection_states[connection_id]