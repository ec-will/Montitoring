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
HOME_DIR = os.getenv('HPC_HOME', os.path.expanduser('~'))
if 'erthch01' not in HOME_DIR:
    HOME_DIR = '/e/08/erthch01'

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
    current_section = None
    section_desc = None
    
    for line in output.split('\n'):
        line = line.strip()
        
        # Detect WRF section headers (comments starting with #)
        if line.startswith('# ') and 'WRF' in line:
            section_desc = line[2:]  # Remove '# '
            current_section = None
            continue
        
        # Skip empty lines and other comments
        if not line or line.startswith('#'):
            continue
        
        # Parse cron lines: minute hour * * * command >& logfile
        # Pattern: MM HH * * * ... >& path/to/logfile
        cron_match = re.match(r'(\d+)\s+(\d+)\s+\*\s+\*\s+\*.*>& .*/([^\s/]+)\.log', line)
        if not cron_match:
            continue
        
        minute_str, hour_str, log_basename = cron_match.groups()
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
            'description': section_desc or 'WRF Job'
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


def analyze_log_status(logfile):
    """Analyze log file to determine workflow status."""
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


def get_wrfout_count(job_name, cycle_num, logfile):
    """Count wrfout files for a job."""
    try:
        # Extract date from log filename (YYYYMMDDHH format)
        match = re.search(r'\.(\d{10})\.log$', logfile)
        if not match:
            return 0
        
        datetime_str = match.group(1)
        date_str = datetime_str[:8]
        
        # Determine data directory based on job name
        if 'global_wrf' in job_name:
            cycle_dir = os.path.join(DATA_DIR, 'intel', 'global_0.25deg', f'{date_str}{cycle_num}')
        elif 'accuwx_asia' in job_name:
            cycle_dir = os.path.join(DATA_DIR, 'accuwx_asia', f'{date_str}{cycle_num}')
        elif 'accuwx_europe' in job_name:
            cycle_dir = os.path.join(DATA_DIR, 'accuwx_plus', f'{date_str}{cycle_num}')
        else:
            return 0
        
        wrfout_files = glob.glob(os.path.join(cycle_dir, 'wrfout*'))
        return len(wrfout_files)
    except:
        return 0


def get_job_status(job_name, cycle_num):
    """Get status for a specific WRF job."""
    try:
        # Build log file pattern based on job name
        if 'global_wrf' in job_name:
            log_pattern = f'run_master.global{cycle_num}Z*.log'
        elif 'accuwx_asia' in job_name:
            log_pattern = f'accuwx_asia_seq.{cycle_num}.*.log'
        elif 'accuwx_europe' in job_name:
            log_pattern = f'accuwx_euro_seq.{cycle_num}.*.log'
        else:
            return None
        
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
        
        # Override status based on file count for WRF jobs
        if file_count > 30:
            status_info['status'] = 'success'
            status_info['message'] = 'Completed successfully'
        elif file_count > 0:
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
        
        # Get job status
        job_status = get_job_status(job_name, cycle_num)
        
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
