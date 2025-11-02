#!/usr/bin/env python3
import subprocess
import json
import re
import time
import os
import glob
from datetime import datetime, timedelta

# Base directory for HPC user (defaults to /e/08/erthch01 for production)
HOME_DIR = os.getenv('HPC_HOME', os.path.expanduser('~'))
if 'erthch01' not in HOME_DIR:
    # Fallback for production if $HPC_HOME not set
    HOME_DIR = '/e/08/erthch01'

LOGS_DIR = os.path.join(HOME_DIR, 'logs')
WRF_LOGS_DIR = os.path.join(LOGS_DIR, 'wrf')
DATA_DIR = os.path.join(HOME_DIR, 'data')

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

def analyze_log_status(logfile):
    """Analyze log file to determine workflow status"""
    try:
        if not os.path.isfile(logfile):
            return {'status': 'no_log', 'message': 'No log file found', 'details': ''}
        
        with open(logfile, 'r') as f:
            tail_content = f.read()
        
        # Check for clear failure indicators
        if re.search(r'killed|abort|fatal|exception', tail_content, re.IGNORECASE):
            error_msg = re.search(r'(killed|abort|fatal|exception)[^\n]*', tail_content, re.IGNORECASE)
            return {'status': 'failed', 'message': 'Job failed', 'details': error_msg.group(0) if error_msg else ''}
        
        # Check for external data waiting
        if re.search(r'404.*not found.*(nomads|ncep|gfs)', tail_content, re.IGNORECASE):
            age = get_file_age(logfile)
            if age < 30:
                return {'status': 'waiting_data', 'message': 'Waiting for GFS data from NOAA', 'details': 'External data delay'}
            else:
                return {'status': 'failed', 'message': 'Data unavailable', 'details': 'Upstream data timeout'}
        
        # Check for success
        if re.search(r'^exit$|cycle.*complete|processing.*complete', tail_content, re.MULTILINE):
            return {'status': 'success', 'message': 'Job completed successfully', 'details': 'Normal completion'}
        
        # Check for active running state
        age = get_file_age(logfile)
        if age < 5 and re.search(r'still waiting|qsub|date.*UTC|PBS', tail_content, re.IGNORECASE):
            return {'status': 'running', 'message': 'Job currently running', 'details': 'Active processing'}
        
        # Default running or unknown
        if age < 30:
            return {'status': 'running', 'message': 'Job appears to be running', 'details': 'Recent activity detected'}
        else:
            return {'status': 'unknown', 'message': 'Status unclear', 'details': 'No recent activity'}
    except:
        return {'status': 'unknown', 'message': 'Error analyzing log', 'details': ''}

def get_file_age(filepath):
    """Get file age in minutes"""
    try:
        file_time = os.path.getmtime(filepath)
        return int((time.time() - file_time) / 60)
    except:
        return 999

def get_last_run_from_log(logfile):
    """Extract last run time from log filename"""
    try:
        basename = os.path.basename(logfile)
        # Pattern: run_master.globalXXZ.XXhr.XXXXXXXXXX.log or accuwx_*_seq.XX.XXXXXXXXXX.log
        match = re.search(r'\.(\d{10})\.log$', basename)
        if match:
            timestamp_str = match.group(1)
            # Convert Unix timestamp to readable format
            timestamp = int(timestamp_str)
            dt = datetime.utcfromtimestamp(timestamp)
            age_minutes = int((time.time() - timestamp) / 60)
            if age_minutes < 1:
                return f'Just now', age_minutes
            elif age_minutes < 60:
                return f'{age_minutes}m ago', age_minutes
            elif age_minutes < 1440:
                hours = age_minutes // 60
                return f'{hours}h ago', age_minutes
            else:
                days = age_minutes // 1440
                return f'{days}d ago', age_minutes
    except:
        pass
    return 'N/A', 999

def update_wrf_cycle_status(workflow_data, cycle_num):
    """Update status and file count for a specific WRF cycle (00, 06, 12, 18)"""
    try:
        log_pattern = f'run_master.global{cycle_num}Z*.log'
        log_files = sorted(glob.glob(os.path.join(WRF_LOGS_DIR, log_pattern)), reverse=True)
        
        if log_files:
            latest_log = log_files[0]
            match = re.search(r'run_master\.global\d{2}Z\.(\d{2})hr\.(\d{10})\.log', latest_log)
            if match:
                datetime_str = match.group(2)
                date_str = datetime_str[:8]
                cycle_dir = os.path.join(DATA_DIR, 'intel', 'global_0.25deg', f'{date_str}{cycle_num}')
                
                wrfout_files = glob.glob(f'{cycle_dir}/wrfout*')
                file_count = len(wrfout_files)
                workflow_data['file_count'] = file_count
                
                # Get last run time from log filename
                last_run_str, age = get_last_run_from_log(latest_log)
                workflow_data['last_run'] = last_run_str
                
                # Update status from log analysis
                status_info = analyze_log_status(latest_log)
                workflow_data['status'] = status_info
                
                # Override status based on file count for WRF jobs
                if file_count > 30:
                    workflow_data['status']['status'] = 'success'
                    workflow_data['status']['message'] = 'Completed successfully'
                elif file_count > 0:
                    workflow_data['status']['status'] = 'running'
                    workflow_data['status']['message'] = 'Currently running'
    except Exception as e:
        pass

def get_workflows():
    """Get model run status (WRF-based workflows only) - collect directly from logs"""
    model_runs = {}
    
    try:
        # Process global WRF variants (00Z, 06Z, 12Z, 18Z)
        for cycle in ['00Z', '06Z', '12Z', '18Z']:
            variant_name = f'global_wrf_{cycle}'
            cycle_num = cycle.replace('Z', '')
            
            model_runs[variant_name] = {
                'status': {'status': 'unknown', 'message': 'Status unknown'},
                'file_count': 0,
                'log_file': None,
                'last_run': 'N/A',
                'next_run': get_dynamic_next_run(variant_name),
                'cycle': cycle_num
            }
            
            update_wrf_cycle_status(model_runs[variant_name], cycle_num)
            
            # Try to get log content
            log_pattern = f'run_master.global{cycle_num}Z*.log'
            log_files = sorted(glob.glob(os.path.join(WRF_LOGS_DIR, log_pattern)), reverse=True)
            if log_files:
                latest_log = log_files[0]
                model_runs[variant_name]['log_file'] = os.path.basename(latest_log)
                try:
                    with open(latest_log, 'r') as f:
                        content = f.read()
                    model_runs[variant_name]['log_content'] = content[-500:] if len(content) > 500 else content
                except:
                    model_runs[variant_name]['log_content'] = 'Could not read log file'
        
        # Process AccuWeather Asia
        model_runs['accuwx_asia'] = {
            'status': {'status': 'unknown', 'message': 'Status unknown'},
            'file_count': 0,
            'log_file': None,
            'last_run': 'N/A',
            'next_run': get_dynamic_next_run('accuwx_asia')
        }
        
        asia_logs = sorted(glob.glob(os.path.join(WRF_LOGS_DIR, 'accuwx_asia_seq*.log')), reverse=True)
        if asia_logs:
            latest_log = asia_logs[0]
            model_runs['accuwx_asia']['log_file'] = os.path.basename(latest_log)
            model_runs['accuwx_asia']['status'] = analyze_log_status(latest_log)
            
            # Get last run time
            last_run_str, _ = get_last_run_from_log(latest_log)
            model_runs['accuwx_asia']['last_run'] = last_run_str
            
            # Count wrfout files
            match = re.search(r'accuwx_asia_seq\.(\d{2})\.(\d{10})\.log', latest_log)
            if match:
                datetime_str = match.group(2)
                date_str = datetime_str[:8]
                cycle = match.group(1)
                cycle_dir = os.path.join(DATA_DIR, 'accuwx_asia', f'{date_str}{cycle}')
                wrfout_files = glob.glob(f'{cycle_dir}/wrfout*')
                model_runs['accuwx_asia']['file_count'] = len(wrfout_files)
            
            try:
                with open(latest_log, 'r') as f:
                    content = f.read()
                model_runs['accuwx_asia']['log_content'] = content[-500:] if len(content) > 500 else content
            except:
                model_runs['accuwx_asia']['log_content'] = 'Could not read log file'
        
        # Process AccuWeather Europe
        model_runs['accuwx_europe'] = {
            'status': {'status': 'unknown', 'message': 'Status unknown'},
            'file_count': 0,
            'log_file': None,
            'last_run': 'N/A',
            'next_run': get_dynamic_next_run('accuwx_europe')
        }
        
        euro_logs = sorted(glob.glob(os.path.join(WRF_LOGS_DIR, 'accuwx_euro_seq*.log')), reverse=True)
        if euro_logs:
            latest_log = euro_logs[0]
            model_runs['accuwx_europe']['log_file'] = os.path.basename(latest_log)
            model_runs['accuwx_europe']['status'] = analyze_log_status(latest_log)
            
            # Get last run time
            last_run_str, _ = get_last_run_from_log(latest_log)
            model_runs['accuwx_europe']['last_run'] = last_run_str
            
            # Count wrfout files
            match = re.search(r'accuwx_euro_seq\.(\d{2})\.(\d{10})\.log', latest_log)
            if match:
                datetime_str = match.group(2)
                date_str = datetime_str[:8]
                cycle = match.group(1)
                cycle_dir = os.path.join(DATA_DIR, 'accuwx_plus', f'{date_str}{cycle}')
                wrfout_files = glob.glob(f'{cycle_dir}/wrfout*')
                model_runs['accuwx_europe']['file_count'] = len(wrfout_files)
            
            try:
                with open(latest_log, 'r') as f:
                    content = f.read()
                model_runs['accuwx_europe']['log_content'] = content[-500:] if len(content) > 500 else content
            except:
                model_runs['accuwx_europe']['log_content'] = 'Could not read log file'
        
        return model_runs
    except Exception as e:
        print(f"Error getting model runs: {e}")
        return {}

def get_dynamic_next_run(workflow_name):
    """Calculate next run time based on actual cron schedules"""
    now = datetime.utcnow()
    current_hour = now.hour
    current_minute = now.minute
    
    if workflow_name == 'global_wrf' or workflow_name.startswith('global_wrf_'):
        cycle_schedule = {
            'global_wrf_00Z': (1, 25),
            'global_wrf_06Z': (7, 25),
            'global_wrf_12Z': (13, 25),
            'global_wrf_18Z': (19, 15)
        }
        
        if workflow_name in cycle_schedule:
            target_hour, target_minute = cycle_schedule[workflow_name]
        else:
            return "Unknown schedule"
        
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        if target_time > now:
            next_time = target_time
        else:
            next_time = (now + timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_asia':
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
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=29, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    elif workflow_name == 'accuwx_europe':
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
            next_time = (now + timedelta(days=1)).replace(hour=4, minute=28, second=0, microsecond=0)
            
        if next_time.date() == now.date():
            return f"Today {next_time.strftime('%H:%M')}"
        else:
            return f"Tomorrow {next_time.strftime('%H:%M')}"
    
    else:
        return "Unknown schedule"

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

# Generate the complete dashboard data
dashboard_data = {
    'system': get_system_info(),
    'workflows': get_workflows(),
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
