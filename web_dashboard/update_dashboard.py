#!/usr/bin/env python3
import subprocess
import json
import re
import time
from datetime import datetime

def get_pbs_jobs():
    """Get PBS jobs with correct core calculation and wallclock time"""
    try:
        output = subprocess.check_output(['qstat', '-f', '-u', 'erthch01'], stderr=subprocess.DEVNULL).decode()
    except:
        return []
    
    jobs = []
    current_job = {}
    
    for line in output.split('\n'):
        # Job ID
        job_match = re.match(r'Job Id: (\d+)\.', line)
        if job_match:
            if current_job.get('job_id'):
                jobs.append(current_job)
            current_job = {'job_id': job_match.group(1)}
            continue
            
        # Job properties
        if 'Job_Name = ' in line:
            current_job['name'] = line.split(' = ', 1)[1]
        elif 'job_state = ' in line:
            current_job['state'] = line.split(' = ', 1)[1]
        elif 'resources_used.walltime = ' in line:
            current_job['walltime'] = line.split(' = ', 1)[1]
        elif 'Resource_List.nodes = ' in line:
            # Only parse the first Resource_List.nodes line
            nodes_spec = line.split(' = ', 1)[1]
            
            # Parse like: 2:erthch:ppn=16
            node_match = re.match(r'(\d+):([^:]+):ppn=(\d+)', nodes_spec.strip())
            if node_match:
                node_count = int(node_match.group(1))
                ppn = int(node_match.group(3))
                current_job['nodes'] = node_count
                current_job['tasks'] = node_count * ppn
    
    # Add last job
    if current_job.get('job_id'):
        jobs.append(current_job)
    
    
    # Get detailed mqstat info for each job
    for job in jobs:
        try:
            mqstat_output = subprocess.check_output(['mqstat', '-f', job['job_id']], stderr=subprocess.DEVNULL).decode().strip()
            job['mqstat_details'] = mqstat_output
        except:
            job['mqstat_details'] = f"Unable to retrieve detailed information for job {job['job_id']}"
    
    return jobs

def get_node_status():
    """Get node status from ectnodes command and parse into structured data"""
    try:
        output = subprocess.check_output(['/e/08/erthch01/bin/ectnodes'], stderr=subprocess.DEVNULL).decode().strip()
        
        # Parse the ectnodes output into structured data
        nodes = []
        lines = output.split('\n')
        
        for line in lines:
            # Skip header lines and separator lines
            if 'Node Name' in line or '----' in line or 'TOTALS' in line or not line.strip():
                continue
            
            # Parse node data lines like: "n619007         16     16     0        "
            parts = line.split()
            if len(parts) >= 4:
                nodes.append({
                    'name': parts[0],
                    'total': int(parts[1]),
                    'used': int(parts[2]),
                    'available': int(parts[3])
                })
        
        # Calculate totals
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
            'raw_output': output  # Keep raw output as backup
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
        # Use find to search recursively for the log file
        output = subprocess.check_output(['find', '/e/08/erthch01/logs', '-name', log_filename, '-type', 'f'], 
                                       stderr=subprocess.DEVNULL).decode().strip()
        if output:
            return output.split('\n')[0]  # Return first match
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
    
    df_output = subprocess.check_output(['df', '-h', '/e/08/erthch01']).decode().split('\n')[1]
    disk_parts = df_output.split()
    disk_usage = disk_parts[2] + '/' + disk_parts[1]
    disk_percent = int(disk_parts[4].replace('%', ''))
    
    free_output = subprocess.check_output(['free', '-h']).decode().split('\n')[1]
    mem_parts = free_output.split()
    
    log_count = 0
    try:
        log_count = int(subprocess.check_output(['find', '/e/08/erthch01/logs', '-name', '*.log', '-mmin', '-60'], stderr=subprocess.DEVNULL).decode().count('\n'))
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
    """Get workflow status from original script and add real log content"""
    try:
        output = subprocess.check_output(['../scripts/dashboard_json.sh', '--json'], stderr=subprocess.DEVNULL)
        data = json.loads(output)
        workflows = data.get('workflows', {})
        
        # Add next run times and real log content
        for workflow_name, workflow_data in workflows.items():
            # Add next run times
            if workflow_name == 'global_wrf':
                workflow_data['next_run'] = get_dynamic_next_run('global_wrf')
            elif workflow_name == 'accuwx_asia':
                workflow_data['next_run'] = get_dynamic_next_run('accuwx_asia')
            elif workflow_name == 'accuwx_europe':
                workflow_data['next_run'] = get_dynamic_next_run('accuwx_europe')
            elif workflow_name == 'mrms':
                workflow_data['next_run'] = get_dynamic_next_run('mrms')
            elif workflow_name == 'drone_weather':
                workflow_data['next_run'] = get_dynamic_next_run('drone_weather')
            
            # Get real log content
            log_file = workflow_data.get('log_file')
            if log_file:
                log_content = get_workflow_log_content(log_file)
                if log_content:
                    workflow_data['log_content'] = log_content
                else:
                    workflow_data['log_content'] = f"Log file not found: {log_file}"
            
        return workflows
    except Exception as e:
        print(f"Error getting workflows: {e}")
        return {}
def get_dynamic_next_run(workflow_name):
    """Calculate next run time based on actual cron schedules"""
    import subprocess
    from datetime import datetime, timedelta
    
    # Get current UTC time
    now = datetime.utcnow()
    current_hour = now.hour
    current_minute = now.minute
    
    if workflow_name == 'global_wrf':
        # Runs at minutes 01 of hours: 06,07,08,09,11,13,15,16,17,18,20,22
        hours = [6, 7, 8, 9, 11, 13, 15, 16, 17, 18, 20, 22]
        minute = 1
        
        # Find next scheduled hour
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
        else:
            # Next run is tomorrow at first hour (06:01)
            next_time = (now + timedelta(days=1)).replace(hour=6, minute=1, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_asia':
        # Runs at 29 minutes past hours: 04, 10, 16, 22 UTC
        hours = [4, 10, 16, 22]
        minute = 29
        
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
        else:
            # Next run is tomorrow at 04:29
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=29, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_europe':
        # Runs at 28 minutes past hours: 04, 10, 16, 22 UTC  
        hours = [4, 10, 16, 22]
        minute = 28
        
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
        else:
            # Next run is tomorrow at 04:28
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=28, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'mrms':
        # Runs every 5 minutes at: 01,06,11,16,21,26,31,36,41,46,51,56
        minutes = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]
        
        next_minute = None
        for minute in minutes:
            if minute > current_minute:
                next_minute = minute
                break
        
        if next_minute is not None:
            next_time = now.replace(minute=next_minute, second=0, microsecond=0)
        else:
            # Next run is next hour at minute 01
            next_time = (now + timedelta(hours=1)).replace(minute=1, second=0, microsecond=0)
            
        time_diff = (next_time - now).total_seconds() / 60
        if time_diff <= 60:
            return f"In {int(time_diff)} min"
        else:
            return "Every 5 minutes"
    
    elif workflow_name == 'drone_weather':
        # Runs at minute 10 of every hour
        minute = 10
        
        if minute > current_minute:
            next_time = now.replace(minute=minute, second=0, microsecond=0)
        else:
            next_time = (now + timedelta(hours=1)).replace(minute=minute, second=0, microsecond=0)
            
        time_diff = (next_time - now).total_seconds() / 60
        if time_diff <= 60:
            return f"In {int(time_diff)} min"
        else:
            return "Hourly"
    
    else:
        return "Unknown schedule"


def get_dynamic_next_run(workflow_name):
    """Calculate next run time based on actual cron schedules"""
    import subprocess
    from datetime import datetime, timedelta
    
    # Get current UTC time
    now = datetime.utcnow()
    current_hour = now.hour
    current_minute = now.minute
    
    if workflow_name == 'global_wrf':
        # Runs at minutes 01 of hours: 06,07,08,09,11,13,15,16,17,18,20,22
        hours = [6, 7, 8, 9, 11, 13, 15, 16, 17, 18, 20, 22]
        minute = 1
        
        # Find next scheduled hour
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
        else:
            # Next run is tomorrow at first hour (06:01)
            next_time = (now + timedelta(days=1)).replace(hour=6, minute=1, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_asia':
        # Runs at 29 minutes past hours: 04, 10, 16, 22 UTC
        hours = [4, 10, 16, 22]
        minute = 29
        
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
        else:
            # Next run is tomorrow at 04:29
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=29, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_europe':
        # Runs at 28 minutes past hours: 04, 10, 16, 22 UTC  
        hours = [4, 10, 16, 22]
        minute = 28
        
        next_hour = None
        for hour in hours:
            if hour > current_hour or (hour == current_hour and minute > current_minute):
                next_hour = hour
                break
        
        if next_hour is not None:
            next_time = now.replace(hour=next_hour, minute=minute, second=0, microsecond=0)
        else:
            # Next run is tomorrow at 04:28
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=28, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'mrms':
        # Runs every 5 minutes at: 01,06,11,16,21,26,31,36,41,46,51,56
        minutes = [1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56]
        
        next_minute = None
        for minute in minutes:
            if minute > current_minute:
                next_minute = minute
                break
        
        if next_minute is not None:
            next_time = now.replace(minute=next_minute, second=0, microsecond=0)
        else:
            # Next run is next hour at minute 01
            next_time = (now + timedelta(hours=1)).replace(minute=1, second=0, microsecond=0)
            
        time_diff = (next_time - now).total_seconds() / 60
        if time_diff <= 60:
            return f"In {int(time_diff)} min"
        else:
            return "Every 5 minutes"
    
    elif workflow_name == 'drone_weather':
        # Runs at minute 10 of every hour
        minute = 10
        
        if minute > current_minute:
            next_time = now.replace(minute=minute, second=0, microsecond=0)
        else:
            next_time = (now + timedelta(hours=1)).replace(minute=minute, second=0, microsecond=0)
            
        time_diff = (next_time - now).total_seconds() / 60
        if time_diff <= 60:
            return f"In {int(time_diff)} min"
        else:
            return "Hourly"
    
    else:
        return "Unknown schedule"



# Generate the complete dashboard data
dashboard_data = {
    'system': get_system_info(),
    'workflows': get_workflows(),
    'pbs_jobs': get_pbs_jobs(),
    'node_status': get_node_status(),
    'upcoming_jobs': [
        {'name': 'global_wrf_00Z', 'next_run': 'Today 23:30'},
        {'name': 'accuwx_asia_12Z', 'next_run': 'Tomorrow 00:15'},
        {'name': 'accuwx_europe_12Z', 'next_run': 'Tomorrow 00:30'},
        {'name': 'mrms_download', 'next_run': 'Tomorrow 01:00'},
        {'name': 'drone_weather_seq', 'next_run': 'Tomorrow 02:00'},
        {'name': 'cleanup_old_files', 'next_run': 'Tomorrow 03:00'}
    ],
    'cron_summary': {
        'total_jobs': 53,
        'last_updated': int(time.time())
    }
}

# Write JSON file
with open('dashboard_data.json', 'w') as f:
    json.dump(dashboard_data, f, indent=2)

# Test the cores calculation and walltime
print("PBS Jobs with core counts and wallclock time:")
for job in dashboard_data['pbs_jobs']:
    walltime = job.get('walltime', 'N/A')
    print(f"Job {job['job_id']}: {job.get('nodes', 'N/A')} nodes, {job.get('tasks', 'N/A')} cores, {walltime} elapsed")

# Show log file locations found
print(f"\nFound {len(dashboard_data['workflows'])} workflows:")
for name, workflow in dashboard_data['workflows'].items():
    log_file = workflow.get('log_file', 'None')
    file_count = workflow.get('file_count', 'N/A')
    has_content = 'log_content' in workflow and not workflow['log_content'].startswith('Log file not found')
    print(f"  {name}: {file_count} files, log: {'✓' if has_content else '✗'}")

# Show node status summary
node_data = dashboard_data['node_status']
if 'error' not in node_data:
    totals = node_data['totals']
    print(f"\nNode Status: {len(node_data['nodes'])} nodes, {totals['used']}/{totals['total']} cores used")
else:
    print(f"\nNode Status: {node_data['error']}")

print("JSON file generated successfully!")
