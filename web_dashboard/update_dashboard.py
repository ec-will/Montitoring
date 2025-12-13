#!/usr/bin/env python3
import subprocess
import json
import re
import time
import os
import glob
from datetime import datetime, timedelta
from model_runs import get_wrf_model_runs

# Base directory for HPC user
HOME_DIR = os.path.expanduser('~')
LOGS_DIR = os.path.join(HOME_DIR, 'logs')

def get_pbs_jobs():
    """Get PBS jobs with correct core calculation and wallclock time"""
    try:
        output = subprocess.check_output(['qstat', '-f', '-u', 'erthch01'], stderr=subprocess.DEVNULL).decode()
    except:
        return []
    
    jobs = []
    current_job = {}
    
    for line in output.split('\n'):
        job_match = re.match(r'Job Id: (\d+)\.', line)
        if job_match:
            if current_job.get('job_id'):
                jobs.append(current_job)
            current_job = {'job_id': job_match.group(1)}
            continue
            
        if 'Job_Name = ' in line:
            current_job['name'] = line.split(' = ', 1)[1]
        elif 'job_state = ' in line:
            current_job['state'] = line.split(' = ', 1)[1]
        elif 'resources_used.walltime = ' in line:
            current_job['walltime'] = line.split(' = ', 1)[1]
        elif 'Resource_List.nodes = ' in line:
            nodes_spec = line.split(' = ', 1)[1]
            node_match = re.match(r'(\d+):([^:]+):ppn=(\d+)', nodes_spec.strip())
            if node_match:
                node_count = int(node_match.group(1))
                ppn = int(node_match.group(3))
                current_job['nodes'] = node_count
                current_job['tasks'] = node_count * ppn
    
    if current_job.get('job_id'):
        jobs.append(current_job)
    
    for job in jobs:
        try:
            mqstat_output = subprocess.check_output(['mqstat', '-f', job['job_id']], stderr=subprocess.DEVNULL).decode().strip()
            job['mqstat_details'] = mqstat_output
        except:
            job['mqstat_details'] = f"Unable to retrieve detailed information for job {job['job_id']}"
    
    return jobs

def get_node_status():
    """Get node status from ectnodes command"""
    try:
        ectnodes_path = os.path.join(HOME_DIR, 'bin', 'ectnodes')
        output = subprocess.check_output([ectnodes_path], stderr=subprocess.DEVNULL).decode().strip()
        nodes = []
        for line in output.split('\n'):
            if 'Node Name' in line or '----' in line or 'TOTALS' in line or not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 4:
                nodes.append({
                    'name': parts[0],
                    'total': int(parts[1]),
                    'used': int(parts[2]),
                    'available': int(parts[3])
                })
        
        total_cores = sum(node['total'] for node in nodes)
        used_cores = sum(node['used'] for node in nodes)
        available_cores = sum(node['available'] for node in nodes)
        
        return {
            'nodes': nodes,
            'totals': {
                'total': total_cores,
                'used': used_cores,
                'available': available_cores
            },
            'raw_output': output
        }
    except Exception as e:
        return {
            'error': f"Error getting node status: {str(e)}",
            'nodes': [],
            'totals': {'total': 0, 'used': 0, 'available': 0}
        }

def find_log_file(log_filename):
    """Find a log file by searching recursively"""
    try:
        output = subprocess.check_output(['find', LOGS_DIR, '-name', log_filename, '-type', 'f'], 
                                       stderr=subprocess.DEVNULL).decode().strip()
        if output:
            return output.split('\n')[0]
    except:
        pass
    return None

def get_workflow_log_content(log_filename):
    """Get the last 20 lines of a log file"""
    log_path = find_log_file(log_filename)
    if log_path:
        try:
            output = subprocess.check_output(['tail', '-20', log_path], 
                                           stderr=subprocess.DEVNULL).decode().strip()
            return output
        except:
            pass
    return None

def get_system_info():
    """Get system information"""
    uptime_output = subprocess.check_output(['uptime']).decode().strip()
    load_avg = uptime_output.split('load average: ')[1] if 'load average:' in uptime_output else 'N/A'
    
    df_output = subprocess.check_output(['df', '-h', HOME_DIR]).decode().split('\n')[1]
    disk_parts = df_output.split()
    disk_usage = disk_parts[2] + '/' + disk_parts[1]
    disk_percent = int(disk_parts[4].replace('%', ''))
    
    free_output = subprocess.check_output(['free', '-h']).decode().split('\n')[1]
    mem_parts = free_output.split()
    
    log_count = 0
    try:
        log_count = int(subprocess.check_output(['find', LOGS_DIR, '-name', '*.log', '-mmin', '-60'], stderr=subprocess.DEVNULL).decode().count('\n'))
    except:
        pass
    
    return {
        'timestamp': int(time.time()),
        'current_time': datetime.utcnow().strftime('%H:%M') + ' UTC',
        'current_date': datetime.utcnow().strftime('%Y-%m-%d'),
        'uptime': uptime_output,
        'load_average': load_avg,
        'disk': {
            'usage_percent': disk_percent,
            'usage_human': disk_usage
        },
        'memory': {
            'used': mem_parts[2],
            'total': mem_parts[1]
        },
        'recent_log_activity': log_count
    }


def get_workflows():
    """Get model run status from model_runs.py - dynamically discovers from crontab"""
    try:
        return get_wrf_model_runs()
    except Exception as e:
        print(f"Error getting model runs: {e}")
        return {}

def get_upcoming_jobs(hours_ahead=6):
    """Generate upcoming scheduled jobs for the next N hours"""
    now = datetime.utcnow()
    end_time = now + timedelta(hours=hours_ahead)
    upcoming = []
    
    schedules = {
        'accuwx_asia_00Z': {'hours': [4], 'minute': 29, 'name': 'accuwx_asia_00Z'},
        'accuwx_asia_06Z': {'hours': [10], 'minute': 29, 'name': 'accuwx_asia_06Z'},
        'accuwx_asia_12Z': {'hours': [16], 'minute': 29, 'name': 'accuwx_asia_12Z'},
        'accuwx_asia_18Z': {'hours': [22], 'minute': 29, 'name': 'accuwx_asia_18Z'},
        'accuwx_europe_00Z': {'hours': [4], 'minute': 28, 'name': 'accuwx_europe_00Z'},
        'accuwx_europe_06Z': {'hours': [10], 'minute': 28, 'name': 'accuwx_europe_06Z'},
        'accuwx_europe_12Z': {'hours': [16], 'minute': 28, 'name': 'accuwx_europe_12Z'},
        'accuwx_europe_18Z': {'hours': [22], 'minute': 28, 'name': 'accuwx_europe_18Z'},
    }
    
    current_time = now
    while current_time <= end_time:
        for job_id, schedule in schedules.items():
            if current_time.hour in schedule['hours']:
                job_time = current_time.replace(minute=schedule['minute'], second=0, microsecond=0)
                if job_time > now and job_time <= end_time:
                    upcoming.append({
                        'time': job_time,
                        'name': schedule['name'],
                        'formatted_time': format_upcoming_time(job_time, now)
                    })
        
        current_time += timedelta(hours=1)
    
    upcoming.sort(key=lambda x: x['time'])
    return [{'name': job['name'], 'next_run': job['formatted_time']} for job in upcoming[:10]]

def format_upcoming_time(job_time, now):
    """Format upcoming job time for display"""
    time_diff = (job_time - now).total_seconds() / 60
    
    if time_diff < 60:
        return f"In {int(time_diff)} min"
    elif job_time.date() == now.date():
        return f"Today {job_time.strftime('%H:%M')}"
    elif job_time.date() == (now + timedelta(days=1)).date():
        return f"Tomorrow {job_time.strftime('%H:%M')}"
    else:
        return job_time.strftime('%m/%d %H:%M')

# Get workflows and sort by last_run time (most recent first)
workflows = get_workflows()

# Sort workflows by converting last_run strings to comparable values
def get_sort_key(workflow):
    """Convert last_run string to minutes for sorting."""
    last_run = workflow.get('last_run', 'N/A')
    if last_run == 'Just now':
        return 0
    elif 'm ago' in last_run:
        return int(last_run.split('m')[0])
    elif 'h ago' in last_run:
        return int(last_run.split('h')[0]) * 60
    elif 'd ago' in last_run:
        return int(last_run.split('d')[0]) * 1440
    else:
        return 999999  # Put N/A at the end

sorted_workflows = {}
for name in sorted(workflows.keys(), key=lambda k: get_sort_key(workflows[k])):
    sorted_workflows[name] = workflows[name]

# Generate the complete dashboard data
dashboard_data = {
    'system': get_system_info(),
    'workflows': sorted_workflows,
    'pbs_jobs': get_pbs_jobs(),
    'node_status': get_node_status(),
    'upcoming_jobs': get_upcoming_jobs(6),
    'frequent_jobs': [
        {'name': 'mrms_download', 'frequency': 'Every 5 minutes', 'next_run': 'Every 5 min'},
        {'name': 'drone_weather_seq', 'frequency': 'Every hour', 'next_run': 'Hourly'}
    ],
    'cron_summary': {
        'total_jobs': 53,
        'last_updated': int(time.time())
    }
}


# Write JSON file
with open('dashboard_data.json', 'w') as f:
    json.dump(dashboard_data, f, indent=2)

# Debug output
print("PBS Jobs with core counts and wallclock time:")
for job in dashboard_data['pbs_jobs']:
    walltime = job.get('walltime', 'N/A')
    print(f"Job {job['job_id']}: {job.get('nodes', 'N/A')} nodes, {job.get('tasks', 'N/A')} cores, {walltime} elapsed")

print(f"\nFound {len(dashboard_data['workflows'])} workflows:")
for name, workflow in dashboard_data['workflows'].items():
    log_file = workflow.get('log_file', 'None')
    file_count = workflow.get('file_count', 'N/A')
    has_content = 'log_content' in workflow and not workflow['log_content'].startswith('Log file not found')
    print(f"  {name}: {file_count} files, log: {'✓' if has_content else '✗'}")

node_data = dashboard_data['node_status']
if 'error' not in node_data:
    totals = node_data['totals']
    print(f"\nNode Status: {len(node_data['nodes'])} nodes, {totals['used']}/{totals['total']} cores used")
else:
    print(f"\nNode Status: {node_data['error']}")

print("JSON file generated successfully!")
