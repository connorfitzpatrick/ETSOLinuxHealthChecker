# myApp/utils/server_utils.py

import paramiko
import docker
from confluent_kafka import Consumer
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
import time
import logging
from threading import current_thread
from ..shared import redis_client as cache
#from celery import Celery
import asyncssh
import asyncio
import json
import jsonpickle

# TO DO: User Authentication
# Uptime; 
# Patching Information
# Running Services Check (Running within thresholds)
#   -- Should check ntp and chrony
# Network Interface Check
# IDs of users logged into system (Can I do this without root? Can Sudo be used?)

# myApp/utils/server_utils.py
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(threadName)s] %(message)s')
logger = logging.getLogger(__name__)

def get_server_data(server_name):
    data = cache.get(server_name)
    return json.loads(data) if data else {}

def process_server_health_thread(server_name, connection_id):
    # try:
    print("Start process_server_health_thread")
    print(f"Starting health check for {server_name}")
    # Simulate the health check process
    # result = {"status": "Healthy", "last_updated": time.time()}
    result = process_server_health(server_name)
    data = {
        'server_name': server_name,
        'status': result,
        'last_updated': time.time(),
    }

    cache_key = connection_id + "-" + server_name
    # Update server_data in Redis
    print("SETTING CACHE")
    cache.set(cache_key, json.dumps(data))
    print(f"Completed health check for {server_name}: {result}")
    # except Exception as e:
    #     print(f"Exception in process_server_health_thread for {server_name}: {e}")


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
            # Decode the message value from bytes to string, then load it as JSON
            print("MESSAGE RECEIVED")
            message_data = json.loads(msg.value().decode('utf-8'))
            connection_id = message_data['connection_id']
            server_name = message_data['server']

            # This is called for every server name (message) received
            # This submits the process_server_health_thread function 
            # to a thread in the ThreadPoolExecutor for asynchronous execution
            executor.submit(process_server_health_thread, server_name, connection_id)
            print("executed")

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
        return None

def parse_general_info(general_output):
    lines = general_output.strip().split('\n')
    
    # parse date information
    date = lines[0]

    # parse uptime
    uptime_line = lines[1]
    uptime_start_index = uptime_line.find('up ') + len('up')
    uptime_end_index = uptime_line.find(',')
    uptime = uptime_line[uptime_start_index:uptime_end_index].strip()

    # parse users
    users = uptime_line.split(',')[1].strip().split()[0]

    # parse load averages
    load_averages = uptime_line.split(': ')[-1].strip()

    # parse OS information
    os_pretty_name = ''
    for line in lines[2:]:
        if line.startswith('PRETTY_NAME'):
            os_pretty_name = line.split('=')[1].strip('"')
            break
    return (date, uptime, users, load_averages, os_pretty_name)

def parse_inode_health_results(inode_output, server_name):
    lines = inode_output.strip().split('\n')
    state = 'Healthy'
    data = []
    issues = []
    for line in lines[1:]:
        parts = line.split()
        if server_name == "abcdefgh004" and parts[0] == "shm":
            parts[4] = "96%"
        inode_entry = {
            'Filesystem': parts[0],
            'Size': parts[1],
            'Used': parts[2],
            'Avail': parts[3],
            'Use%': parts[4],
            'MountedOn': parts[5],
        }
        if int(parts[4][:-1]) >= 95:
            state = 'Warning'
            issues.append("Inode usage in " + parts[0] + " is currently at " + parts[4])
        data.append(inode_entry)
    
    return (state, issues, data)

def parse_filesystem_health_results(filesystem_output, server_name):
    lines = filesystem_output.strip().split('\n')
    state = 'Healthy'
    data = []
    issues = []

    for line in lines[1:]:
        parts = line.split()
        if server_name == "abcdefgh004" and parts[0] == "/dev/vda1":
            parts[4] = "96%"
        filesystem_entry = {
            'Filesystem': parts[0],
            'Size': parts[1],
            'Used': parts[2],
            'Avail': parts[3],
            'Use%': parts[4],
            'MountedOn': parts[5],
        }
        if int(parts[4][:-1]) >= 95:
            state = 'Warning'
            issues.append("Filesystem usage in " + parts[0] + " is currently at " + parts[4])
        data.append(filesystem_entry)

    return (state, issues, data)

def parse_cpu_usage_health_results(cpu_usage_output):
    lines = cpu_usage_output.strip().split('\n')
    state = 'Healthy'
    data = []
    issues = []

    for line in lines[3:]:
        parts = line.split()
        cpu_usage_entry = {
            'Time': parts[0],
            'CPU': parts[1],
            'User': parts[2],
            'Nice': parts[3],
            'System': parts[4],
            'Iowait': parts[5],
            'Steal': parts[6],
            'Idle': parts[7],
        }
        if int(float(parts[7][:-1])) <= 5:
            state = 'Warning'
            issues.append("Only " + parts[7][:-1] + "% of the CPU is idle")
        data.append(cpu_usage_entry)

    return (state, issues, data)

def parse_server_logs(log_output):
    lines = log_output.strip().split('\n')
    return lines

def parse_server_health_results(outputs, server_name):
    # Parsing logic will go here
    print("MADE IT TO parse_server_health_results")
    results = {}
    # Warning messages will go here
    server_issues = {}

    # parse OS info
    # os_verion = parse_general_info(outputs[0])
    # parse inode health
    # TODO: Parse uptime

    general_server_info = parse_general_info(outputs[1])

    inode_health_results = parse_inode_health_results(outputs[2], server_name)
    # parse filesystem health
    filesystem_health_results = parse_filesystem_health_results(outputs[3], server_name)
    # parse cpu_usage health
    cpu_usage_health_results = parse_cpu_usage_health_results(outputs[4])

    print("MADE IT THROUGH PARSING METHODS")

    overall_health = 'Healthy'
    if inode_health_results[0] != 'Healthy':
        overall_health = 'Warning'
        # server_issues['Inodes'].extend(inode_health_results[1])
        server_issues['Inodes'] = inode_health_results[1]
    if filesystem_health_results[0] != 'Healthy':
        overall_health = 'Warning'
        # server_issues['Filesystems'].extend(filesystem_health_results[1])
        server_issues['Filesystems'] = filesystem_health_results[1]
    if cpu_usage_health_results[0] != 'Healthy':
        overall_health = 'Warning'
        server_issues['CPU Usage'] = cpu_usage_health_results[1]

    # NETWORK: `sar -n EDEV | grep -i average`
    results = {
        'overall_state': overall_health,
        'ping_status': 'Healthy',
        'general_info': {
            'date': general_server_info[0],
            'uptime': general_server_info[1],
            'users': general_server_info[2],
            'load_average': general_server_info[3],
            'operating_system_name': general_server_info[4],
        },
        'inode_info': {
            'inode_health_status': inode_health_results[0],
            'inode_issues': inode_health_results[1],
            'inode_data': inode_health_results[2],
        },
        'filesystem_info': {
            'filesystem_health_status': filesystem_health_results[0],
            'filesystem_issues': filesystem_health_results[1],
            'filesystem_data': filesystem_health_results[2],
        },
        'cpu_use_info': {
            'cpu_use_health_status': cpu_usage_health_results[0],
            'cpu_use_issues': cpu_usage_health_results[1],
            'cpu_use_data': cpu_usage_health_results[2],
        },
        'ntp_info': {
            'ntp_health_status': '',
        },
        'server_issues': server_issues,
        'logs': parse_server_logs(outputs[5]),
    }
    print(results)
    print("END OF PARSING")
    return results

def process_server_health(servers, connection_id):
    print("IN process_server_health() function!")
    # Init SSH Connection Parameters
    hostname = 'localhost'
    username = 'remote_user'
    password = 'password1234'
    
    # Timeout after 40 seconds
    connection_timeout = 10
        
    host_to_port = {}
    # for server in server_list:
    # for server in servers:
    for server in servers:
        cache_key = connection_id + "-" + server
        port = docker_get_host_port(server)
        host_to_port[server] = port

        if not port: 
            result = {
                'overall_state': 'Error',
                'ping_status': 'Error',
                'general_info': {
                    'date': '',
                    'uptime': '',
                    'users': '',
                    'load_average': '',
                    'operating_system_name': '',
                },
                'inode_info': {
                    'inode_health_status': '',
                    'inode_issues': '',
                    'inode_data': '',
                },
                'filesystem_info': {
                    'filesystem_health_status': '',
                    'filesystem_issues': '',
                    'filesystem_data': [],
                },
                'cpu_use_info': {
                    'cpu_use_health_status': '',
                    'cpu_use_issues': '',
                    'cpu_use_data': '',
                },
                'ntp_info': {
                    'ntp_health_status': '',
                },
                'server_issues': {},
                'logs': [],
            }
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # Connect to the Docker container
            # client.connect(hostname, port=port, username=username, password=password, timeout=connection_timeout)
            print("GOING TO TRY TO CONNECT!")
            client.connect(hostname, port=port, username=username, password=password, timeout=connection_timeout)

            commands = (
                    'cat /etc/os-release',
                    'date; uptime; cat /etc/os-release',
                    'df -i',
                    'df -h',
                    'sar -u 2 5',
                    'tail -n 70 /var/log/dpkg.log',
                )
            print("GOING TO RUN COMMANDS")
            delimiter = "END_OF_COMMAND_OUTPUT"
            command = '; echo "{}"; '.format(delimiter).join(commands) + '; echo "{}"'.format(delimiter)
            stdin, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode('utf-8')
                
            outputs = output.split(delimiter)
            # Strip each output to remove leading + trailing whitespace
            outputs = [o.strip() for o in outputs if o.strip()]
            
            # parse output
            result = parse_server_health_results(outputs, server)

            data = {
                'server_name': server,
                'status': result,
                'last_updated': time.time(),
            }
            cache.set(cache_key, json.dumps(data))
            print(f"Completed health check for {server}: {result}")

        except paramiko.ssh_exception.NoValidConnectionsError:
            print(f'Unable to connect to {server} on port 22')
        except paramiko.AuthenticationException:
            print(f'Authentication failed for {server}')
        except Exception as e:
            print(f"Exception in when trying to connect for {server}: {e}")

            data = {
                'server_name': server,
                'status': {
                    'overall_state': 'Error',
                },
                'last_updated': time.time(),
            }
            cache_key = connection_id + "-" + server
            # Update server_data in Redis
            print("SETTING CACHE")
            cache.set(cache_key, json.dumps(data))
                
        # return jsonpickle.encode(results)














# async def process_server_health(server_name):
#     # Init SSH Connection Parameters
#     hostname = 'localhost'
#     username = 'remote_user'
#     password = 'password1234'
    
#     # Timeout after 40 seconds
#     connection_timeout = 10

#     # for server in server_list:
#     port = docker_get_host_port(server_name)
#     if not port: 

#         return {
#             'overall_state': 'Error',
#             'ping_status': 'Error',
#             'general_info': {
#                 'date': '',
#                 'uptime': '',
#                 'users': '',
#                 'load_average': '',
#                 'operating_system_name': '',
#             },
#             'inode_info': {
#                 'inode_health_status': '',
#                 'inode_issues': '',
#                 'inode_data': '',
#             },
#             'filesystem_info': {
#                 'filesystem_health_status': '',
#                 'filesystem_issues': '',
#                 'filesystem_data': [],
#             },
#             'cpu_use_info': {
#                 'cpu_use_health_status': '',
#                 'cpu_use_issues': '',
#                 'cpu_use_data': '',
#             },
#             'ntp_info': {
#                 'ntp_health_status': '',
#             },
#             'server_issues': {},
#             'logs': [],
#         }
#     # Create SSH client
#     # client = paramiko.SSHClient()
#     # client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

#     try:
#         # Connect to the Docker container
#         # client.connect(hostname, port=port, username=username, password=password, timeout=connection_timeout)

#         async with asyncssh.connect(hostname, username=username, password=password) as conn:
#             commands = (
#                 'cat /etc/os-release',
#                 'date; uptime; cat /etc/os-release',
#                 'df -i',
#                 'df -h',
#                 'sar -u 2 5',
#                 'tail -n 70 /var/log/dpkg.log',
#             )
#             command_results = await asyncio.gather(*[conn.run(cmd) for cmd in commands])
            
#             # Process command results
#             results = {}
#             print("COMMAND RESULTS")
#             print(command_results)
#             print("COMMAND RESULTS")

#             # Process command results
#             for cmd, result in zip(commands, command_results):
#                 results[cmd] = result.stdout
            
#             print("COMMAND RESULTS")
#             print(command_results)
#             print("COMMAND RESULTS")

#         return results


#         # Establish SSH connection asynchronously
#         async with asyncssh.connect(hostname, username=username, password=password) as conn:
#             # Run commands asynchronously
#             command_results = await asyncio.gather(
#                 conn.run(commands[0]),
#                 conn.run(commands[1]),
#                 conn.run(commands[2]),
#                 conn.run(commands[3]),
#                 conn.run(commands[4]),
#                 conn.run(commands[5]),
#             )

#         # delimiter = "END_OF_COMMAND_OUTPUT"
#         # command = '; echo "{}"; '.format(delimiter).join(commands) + '; echo "{}"'.format(delimiter)
#         # stdin, stdout, stderr = client.exec_command(command)
#         # output = stdout.read().decode('utf-8')


#         # Split output with delimiter to get a list of command outputs
#         # outputs[1] = inodes
#         # outputs[2] = filesystems
#         # outputs = output.split(delimiter)
#         # Strip each output to remove leading + trailing whitespace
#         # outputs = [o.strip() for o in outputs if o.strip()]
#         # print("received output from VMs?")
#         # parse output
#         # results = parse_server_health_results(outputs, server_name)
#     except paramiko.ssh_exception.NoValidConnectionsError:
#         print(f'Unable to connect to {server_name} on port 22')
#     except paramiko.AuthenticationException:
#         print(f'Authentication failed for {server_name}')
#     except Exception as e:
#         print(f"Exception in when trying to connect for {server_name}: {e}")

#         results = {
#             'overall_state': 'Error',
#         }
    
#     finally:
#         # Close the SSH connection
#         client.close()
        
#     return results