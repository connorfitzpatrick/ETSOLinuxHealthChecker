# myApp/utils/server_utils.py

import paramiko
import docker
from confluent_kafka import Consumer
from threading import Lock
from ..shared_data import server_data
from concurrent.futures import ThreadPoolExecutor
import time

server_data_lock = Lock()

def process_server_health_thread(server_name):
    '''
    This function is a wrapper for the process_server_health function
    to be used in the ThreadPoolExecutor.
    '''
    try:
        print(f"Starting health check for {server_name}")
        result = process_server_health(server_name)
        with server_data_lock:
            # Update server_data with health check results
            server_data[server_name] = {
                # health check results
                'status': result,
                # current timestamp
                'last_updated': time.time()
            }
        print(f"Completed health check for {server_name}: {result}")
    except Exception as e:
        print(f"Exception in process_server_health_thread for {server_name}: {e}")


def start_kafka_consumer():
    '''
    Kafka consumer polls for messages from the message_queue topic.
    '''
    executor = ThreadPoolExecutor(max_workers=10)
    print("Starting Kafka Consumer")

    consumer_config = {
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'server_health_check',
        'auto.offset.reset': 'earliest'
    }
    consumer = Consumer(consumer_config)
    consumer.subscribe(['message_queue'])
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            server_name = msg.value().decode('utf-8')

            # This is called for every server name (message) received
            # This submits the process_server_health_thread function 
            # to a thread in the ThreadPoolExecutor for asynchronous execution
            executor.submit(process_server_health_thread, server_name)

    except Exception as e:
        print(f"Error in Kafka consumer thread: {e}")
    finally:
        consumer.close()
        executor.shutdown()

def docker_get_host_port(container_name):
    '''
    Since I am using a bunch of docker containers to simulate having several Linux servers on
    my network, I need this function to ask docker what port that specific container resides
    on. This is more for dev purposes.
    '''
    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
        ports = container.attrs['NetworkSettings']['Ports']
        for container_port, host_ports in ports.items():
            if host_ports:
                host_port = host_ports[0]['HostPort']
                print(f"  Container Port {container_port}/tcp is mapped to Host Port {host_port}")
                return host_port
            else:
                print(f"  Container Port {container_port}/tcp is not mapped to any Host Port")

    except docker.errors.NotFound:
        print(f"Container '{container_name}' not found.")

# def parse_server_health_results(results):
#     parsed_results = {}
#     # Parsing logic will go here
#     return parsed_results

def process_server_health(server):
    results = {}
    print("Starting the health check processing:")

    # Init SSH Connection Parameters
    hostname = 'localhost'
    username = 'remote_user'
    password = 'password1234'
    print(server)

    # for server in server_list:
    port = docker_get_host_port(server)

    # Create SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # Connect to the Docker container
        client.connect(hostname, port=port, username=username, password=password)

        # Run the 'df -i' command
        # command = 'df -i; cat /etc/os-release'
        command = 'df -i'
        stdin, stdout, stderr = client.exec_command(command)
        output = stdout.read().decode('utf-8')
        print(output)
        # process inode usage
        lines = output.split('\n')
        header = lines[0]
        state = 'healthy'
        unhealthy_filesystems = []

        # Skip header and interate through each filesystem.
        for line in lines[1:-1]:
        # Split each line into columns
            columns = line.split()
    
            if len(columns) >= 6:
                iuse_percentage_str = columns[4].replace('%', '')
                
                try:
                    iuse_percentage = int(iuse_percentage_str)
                    print(iuse_percentage)
                except ValueError:
                    print(f"Error: Invalid IUse% value - {iuse_percentage_str}")
                    continue
                if iuse_percentage >= 95:
                    unhealthy_filesystems.append([columns[0], columns[4]])
                    state = 'Warning'
            else:
                print("Error: Invalid 'df -i' output format")
        print(state)

        results = {
            'state': state,
            'unhealthy_filesystems': unhealthy_filesystems,
            'inodes': output
        }

    finally:
        # Close the SSH connection
        client.close()
        
    return results