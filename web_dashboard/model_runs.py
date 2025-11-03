#!/usr/bin/env python3
"""
WRF Model Runs Discovery and Status Module

Dynamically discovers WRF jobs from crontab and collects their status.
No hardcoded job names or schedules - all from crontab parsing.
"""

import subprocess
import re
import os
import glob
import time
from datetime import datetime, timedelta

# Base directory for HPC user
HOME_DIR = os.path.expanduser('~')
LOGS_DIR = os.path.join(HOME_DIR, 'logs', 'wrf')
DATA_DIR = os.path.join(HOME_DIR, 'data')


def parse_wrf_crontab():
    """
    Parse crontab to discover WRF jobs and their schedules.
    
    Returns:
        dict: {
            'global_wrf_00Z': {'schedule': (1, 25), 'description': 'Global WRF run, prep and postprocessing'},
            'accuwx_asia_00Z': {'schedule': (4, 29), 'description': 'Asia WRF run, prep and postprocessing'},
            ...
        }
    """
    try:
        output = subprocess.check_output(['crontab', '-l'], stderr=subprocess.DEVNULL).decode()
    except:
        return {}
    
    wrf_jobs = {}
    
    for line in output.split('\n'):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        
        # Parse cron lines: minute hour * * * command >& logfile
        # Extract time and log basename
        time_match = re.match(r'(\d+)\s+(\d+)\s+\*\s+\*\s+\*', line)
        if not time_match:
            continue
        
        minute_str, hour_str = time_match.groups()
        
        # Extract log basename from >& path/logname
        log_match = re.search(r'>& .*/([^\s/>`]+)(?:\.log|`[^`]*`\.log)', line)
        if not log_match:
            continue
        
        log_basename = log_match.group(1)
        minute = int(minute_str)
        hour = int(hour_str)
        
        # Extract job name and cycle from log basename
        # Examples: run_master.global00Z, accuwx_asia_seq.00, accuwx_euro_seq.12
        job_match = re.search(r'(run_master\.global|accuwx_asia_seq|accuwx_euro_seq)', log_basename)
        if not job_match:
            continue
        
        job_prefix = job_match.group(1)
        
        # Extract cycle (00Z, 06Z, 12Z, 18Z or 00, 06, 12, 18)
        cycle_match = re.search(r'(00|06|12|18)(?:Z)?', log_basename)
        if not cycle_match:
            continue
        
        cycle_num = cycle_match.group(1)
        cycle_z = f'{cycle_num}Z'
        
        # Build job name
        if 'global' in job_prefix:
            job_name = f'global_wrf_{cycle_z}'
        elif 'accuwx_asia' in job_prefix:
            job_name = f'accuwx_asia_{cycle_z}'
        elif 'accuwx_euro' in job_prefix:
            job_name = f'accuwx_europe_{cycle_z}'
        else:
            continue
        
        wrf_jobs[job_name] = {
            'schedule': (hour, minute),
            'cycle': cycle_num,
            'log_basename': log_basename,  # Store the log file basename from crontab
            'description': 'WRF Job'
        }
    
    return wrf_jobs


def get_file_age(filepath):
    """Get file age in minutes."""
    try:
        file_time = os.path.getmtime(filepath)
        return int((time.time() - file_time) / 60)
    except:
        return 999


def get_last_run_from_log(logfile):
    """Get last run time from log file modification time."""
    try:
        file_mtime = os.path.getmtime(logfile)
        age_seconds = time.time() - file_mtime
        age_minutes = int(age_seconds / 60)
        
        if age_minutes < 1:
            return 'Just now', age_minutes
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


def check_pbs_job_running(job_id):
    """Check if a PBS job is currently running using mqstat."""
    try:
        output = subprocess.check_output(['mqstat', '-f', str(job_id)], stderr=subprocess.DEVNULL).decode()
        # If mqstat returns data without error, job exists and might be running
        if 'job_state' in output:
            # Extract job state
            state_match = re.search(r'job_state\s*=\s*(\w+)', output)
            if state_match:
                state = state_match.group(1)
                return state in ['Q', 'R', 'H']  # Queued, Running, or Held
        return False
    except:
        return False

def analyze_log_status(logfile):
    """Analyze log file to determine workflow status."""
    try:
        if not os.path.isfile(logfile):
            return {'status': 'no_log', 'message': 'No log file found', 'details': ''}
        
        with open(logfile, 'r') as f:
            tail_content = f.read()
        
        # Extract PBS job ID from log if present
        job_id_match = re.search(r'Your job (\d+)', tail_content)
        if job_id_match:
            job_id = job_id_match.group(1)
            if check_pbs_job_running(job_id):
                return {'status': 'running', 'message': 'PBS job currently running', 'details': f'Job ID: {job_id}'}
        
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
        
        # Check for actual success (look for mail commands or cycle completion in output)
        if re.search(r'mail -s.*cycle complete|cycle.*complete|All.*complete', tail_content, re.IGNORECASE):
            return {'status': 'success', 'message': 'Job completed successfully', 'details': 'Normal completion'}
        
        # Check for recent log activity with "still waiting" pattern
        age = get_file_age(logfile)
        if age < 60 and re.search(r'still waiting', tail_content, re.IGNORECASE):
            return {'status': 'running', 'message': 'Job currently running', 'details': 'Still waiting for output'}
        
        # Default based on file age
        if age < 30:
            return {'status': 'unknown', 'message': 'Status unclear', 'details': 'Recent activity but no clear status'}
        else:
            return {'status': 'success', 'message': 'Job completed', 'details': 'No recent activity, assuming completion'}
    except:
        return {'status': 'unknown', 'message': 'Error analyzing log', 'details': ''}


def get_wrfout_count(job_name, cycle_num, logfile):
    """Count wrfout files for a job by extracting working directory from log.
    
    Dynamically finds the working directory from log file contents (WRFHOME, cd commands)
    and counts wrfout files there. No hardcoded paths.
    """
    try:
        # Read log file to find actual working directory
        with open(logfile, 'r') as f:
            log_content = f.read()
        
        # Extract working directory from log file
        # Look for patterns like:
        # - "setenv WRFHOME /path/to/workdir"
        # - "cd /path/to/workdir"
        # - "mkdir -p /path/to/workdir"
        
        working_dir = None
        
        # Try different patterns to find the working directory
        patterns = [
            r'setenv\s+WRFHOME\s+(\S+)',  # setenv WRFHOME /path
            r'cd\s+(\S+/\d{10})\s*$',     # cd /path/YYYYMMDDHH
            r'mkdir\s+-p\s+(\S+/\d{10})', # mkdir -p /path/YYYYMMDDHH
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_content, re.MULTILINE)
            if match:
                working_dir = match.group(1)
                break
        
        if not working_dir or not os.path.exists(working_dir):
            return 0
        
        # Count wrfout files in the working directory
        wrfout_files = glob.glob(os.path.join(working_dir, 'wrfout*'))
        return len(wrfout_files)
    except:
        return 0


def get_job_status(job_name, log_basename, cycle_num):
    """Get status for a specific WRF job.
    
    Args:
        job_name: Job identifier (e.g., 'global_wrf_00Z')
        log_basename: Log file basename from crontab (e.g., 'run_master.global00Z.36hr')
        cycle_num: Cycle number (e.g., '00')
    """
    try:
        # Build log file pattern from basename extracted from crontab
        # The crontab logs use a timestamp in the filename, so we search for
        # log_basename followed by any date/time and .log extension
        log_pattern = f'{log_basename}*.log'
        
        # Find latest log file
        log_files = sorted(glob.glob(os.path.join(LOGS_DIR, log_pattern)), reverse=True)
        if not log_files:
            return {
                'status': {'status': 'no_log', 'message': 'No log file found', 'details': ''},
                'file_count': 0,
                'last_run': 'N/A',
                'log_file': None
            }
        
        latest_log = log_files[0]
        
        # Get status from log analysis
        status_info = analyze_log_status(latest_log)
        
        # Get file count
        file_count = get_wrfout_count(job_name, cycle_num, latest_log)
        
        # Get last run time
        last_run_str, age = get_last_run_from_log(latest_log)
        
        # Override status based on file count for WRF jobs, but only if log shows completion
        if file_count > 30 and status_info['status'] in ['success', 'unknown']:
            # Only mark as success if log analysis already suggests completion or unclear state
            status_info['status'] = 'success'
            status_info['message'] = 'Completed successfully'
        elif file_count > 0 and status_info['status'] == 'unknown':
            # Only override unknown status with running if files exist
            status_info['status'] = 'running'
            status_info['message'] = 'Currently running'
        
        # Get log content
        try:
            with open(latest_log, 'r') as f:
                content = f.read()
            log_content = content[-500:] if len(content) > 500 else content
        except:
            log_content = 'Could not read log file'
        
        return {
            'status': status_info,
            'file_count': file_count,
            'last_run': last_run_str,
            'log_file': os.path.basename(latest_log),
            'log_content': log_content
        }
    except Exception as e:
        return None


def get_next_run(job_name, schedule):
    """Calculate next run time based on cron schedule."""
    now = datetime.utcnow()
    target_hour, target_minute = schedule
    
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if target_time > now:
        next_time = target_time
    else:
        next_time = (now + timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if next_time.date() == now.date():
        return f"Today {next_time.strftime('%H:%M')}"
    else:
        return f"Tomorrow {next_time.strftime('%H:%M')}"


def get_wrf_model_runs():
    """
    Discover and collect status for all WRF model runs.
    
    Returns:
        dict: Dictionary of model runs with their status data
    """
    # Discover jobs from crontab
    wrf_jobs_config = parse_wrf_crontab()
    
    if not wrf_jobs_config:
        return {}
    
    model_runs = {}
    
    for job_name, config in wrf_jobs_config.items():
        cycle_num = config['cycle']
        schedule = config['schedule']
        log_basename = config['log_basename']
        
        # Get job status
        job_status = get_job_status(job_name, log_basename, cycle_num)
        
        if job_status:
            model_runs[job_name] = {
                'status': job_status['status'],
                'file_count': job_status['file_count'],
                'last_run': job_status['last_run'],
                'next_run': get_next_run(job_name, schedule),
                'cycle': cycle_num,
                'log_file': job_status['log_file'],
                'log_content': job_status['log_content']
            }
    
    return model_runs
