# myApp/utils/server_utils.py
import time
from ..shared import cache
import asyncssh
import asyncio
import json
from flask import jsonify

# TO DO: User Authentication
# Uptime; 
# Patching Information
# Running Services Check (Running within thresholds)
#   -- Should check ntp and chrony
# Network Interface Check
# IDs of users logged into system (Can I do this without root? Can Sudo be used?)

# myApp/utils/server_utils.py

def get_server_data(server_name):
    data = cache.get(server_name)
    return json.loads(data) if data else {}

# def docker_get_host_port(container_name):
#     '''
#     Since I am using a bunch of docker containers to simulate having several Linux servers on
#     my network, I need this function to ask docker what port that specific container resides
#     on. This is more for dev purposes.
#     '''
#     client = docker.from_env()
#     try:
#         container = client.containers.get(container_name)
#         ports = container.attrs['NetworkSettings']['Ports']
#         for container_port, host_ports in ports.items():
#             if host_ports:
#                 host_port = host_ports[0]['HostPort']
#                 print(f"  Container Port {container_port}/tcp is mapped to Host Port {host_port}")
#                 return host_port
#             else:
#                 print(f"  Container Port {container_port}/tcp is not mapped to any Host Port")

#     except docker.errors.NotFound:
#         print(f"Container '{container_name}' not found.")
#         return None

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
    general_server_info = parse_general_info(outputs[1])
    inode_health_results = parse_inode_health_results(outputs[2], server_name)
    filesystem_health_results = parse_filesystem_health_results(outputs[3], server_name)
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

async def process_server_health(servers, connection_id):
    print("IN process_server_health() function!")
    # Init SSH Connection Parameters
    hostname = 'localhost'
    username = 'remote_user'
    password = 'password1234'
    
    # Timeout after 40 seconds
    connection_timeout = 10
    tasks = []

    async def run_health_check(server):
        print("In run_health_check()")
        try:
            # port = docker_get_host_port(server)
            # if not port:
            #     # Handle the case when port is not available
            #     result = {
            #         'server_name': server,
            #         'status': {
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
            #         },
            #         'last_updated': time.time(),
            #     }
            #     cache_key = connection_id + "-" + server
            #     # cache.set(cache_key, json.dumps(result))
            #     cache.set(cache_key, json.dumps(result), timeout=60)
            #     print("No port for " + server)
            #     return result
            # Might want to not use known_hosts=None on prod version
            async with asyncssh.connect(hostname, port=2201, username=username, password=password, known_hosts=None) as conn:
                outputs = []
                for command in (
                    'cat /etc/os-release',
                    'date; uptime; cat /etc/os-release',
                    'df -i',
                    'df -h',
                    'sar -u 2 5',
                    'tail -n 70 /var/log/dpkg.log',
                ):
                    result = await conn.run(command)
                    outputs.append(result.stdout)

                print("To parse_server_health_results")
                result = parse_server_health_results(outputs, server)
                cache_key = connection_id + "-" + server
                print(f"Completed health check for {server}")
                # print(f"Completed health check for {server}: {result['status']}")

                output = {
                    'server_name': server,
                    'status': result,
                    'last_updated': time.time(),
                }
                # cache.set(cache_key, json.dumps(output))
                cache.set(cache_key, json.dumps(output), timeout=60)
                return output
        except (asyncssh.Error, OSError) as e:
            # Handle connection or command execution errors
            print(f"Exception in when trying to connect for {server}: {e}")
            return {
                'server_name': server,
                'status': {
                    'overall_state': 'Error',
                },
                'last_updated': time.time(),
            }
    
    # What is are these 3 lines doing? Is it waiting to send
    # Everything back at same time?
    for server in servers:
        tasks.append(run_health_check(server))
    results = await asyncio.gather(*tasks)

