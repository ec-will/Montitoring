#!/usr/bin/env python3
"""
EarthCast HPC Dashboard - Login Node Job Tracker
Tracks cron jobs that run on the login node (not submitted to cluster)
"""

import subprocess
import json
import time
import os
import re
import signal
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
JSON_FILE = 'dashboard_login_jobs.json'
CHECK_INTERVAL = 1  # Check for running processes every second
DATA_RETENTION_HOURS = 48  # Keep job data for 48 hours
LOCK_FILE = '/tmp/dashboard_login_jobs.lock'

# Job submission commands to detect cluster job scripts
JOB_SUBMISSION_COMMANDS = [
    'qsub',      # PBS/Torque
    'sbatch',    # Slurm
    'msub',      # Moab
    'bsub',      # LSF
    'llsubmit',  # LoadLeveler
]

# Global state
running_jobs = {}  # {script_name: start_time}
completed_jobs = []  # List of completed job records
should_exit = False

def signal_handler(sig, frame):
    """Handle graceful shutdown"""
    global should_exit
    print("\nShutting down gracefully...")
    should_exit = True


def is_cluster_submission_script(script_path):
    """Check if a script submits jobs to the cluster by analyzing its content"""
    try:
        # Try to read the script file
        if not os.path.isfile(script_path):
            # Can't read it, assume it's not a submission script
            return False
        
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Look for job submission commands (including full paths ending with the command)
        for cmd in JOB_SUBMISSION_COMMANDS:
            # Token boundary before and whitespace or EOL after; allow any path ending in the cmd
            pattern = rf'(^|[\s`$|;&()])(?:[\w/.-]*/)?{re.escape(cmd)}(\s|$)'
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False
    except Exception as e:
        # If we can't read the file, assume it's not a submission script
        return False

def find_script_path(script_name, cron_command):
    """Try to find the full path of a script from cron command"""
    # First, check if the script name in the command has a full path
    parts = cron_command.split()
    for part in parts:
        if script_name in part and '/' in part:
            # Extract the path (remove quotes, args, etc.)
            path = part.strip('"\' ').split()[0]
            # Expand environment variables like $HOME
            path = os.path.expandvars(path)
            if os.path.isfile(path):
                return path
    
    # Try common locations
    home = os.path.expanduser('~')
    search_paths = [
        f'{home}/monitoring/{script_name}',
        f'{home}/monitoring/web_dashboard/{script_name}',
        f'{home}/scripts/{script_name}',
        f'{home}/{script_name}',
    ]
    
    # Also search in subdirectories of ~/scripts/
    scripts_dir = f'{home}/scripts'
    if os.path.isdir(scripts_dir):
        for subdir in os.listdir(scripts_dir):
            subdir_path = os.path.join(scripts_dir, subdir)
            if os.path.isdir(subdir_path):
                search_paths.append(os.path.join(subdir_path, script_name))
    
    for path in search_paths:
        if os.path.isfile(path):
            return path
    
    # Not found
    return None

def get_login_cron_scripts():
    """Get scripts that run on login node (in cron but not cluster submission scripts)"""
    try:
        result = subprocess.run(['crontab', '-l'], 
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               check=False)
        
        if result.returncode != 0:
            print(f"Warning: Could not read crontab (return code {result.returncode})")
            return set()
        
        login_scripts = set()
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse cron line: minute hour day month weekday command
            parts = line.split()
            if len(parts) >= 6:
                # Command starts at the 6th field
                command = ' '.join(parts[5:])
                
                # Extract script name from command
                for part in command.split():
                    # Skip shell redirectors and operators
                    if part in ['>', '>>', '<', '|', '&', '&&', '||']:
                        continue
                    # Look for something that looks like a script
                    if '/' in part or '.' in part:
                        script_name = os.path.basename(part.strip('"\''))
                        # Remove any trailing arguments
                        script_name = script_name.split()[0]
                        if script_name and not script_name.startswith('-'):
                            # Try to find the full path
                            script_path = find_script_path(script_name, command)
                            
                            if script_path:
                                # Check if it's a cluster submission script
                                if is_cluster_submission_script(script_path):
                                    print(f"  Skipping (submits to cluster): {script_name}")
                                else:
                                    print(f"  Tracking (login node): {script_name}")
                                    login_scripts.add(script_name)
                            else:
                                # Can't find the script, include it anyway
                                print(f"  Tracking (path not found): {script_name}")
                                login_scripts.add(script_name)
                        break
        
        return login_scripts
    except Exception as e:
        print(f"Error reading crontab: {e}")
        return set()

def get_running_processes(username='erthch01'):
    """Get list of currently running processes for the user"""
    try:
        result = subprocess.run(['ps', '-u', username, '-o', 'args='],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True,
                               check=False)
        
        if result.returncode != 0:
            return set()
        
        # Extract script names from command lines
        processes = set()
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Look for script files (.csh, .sh, .py, etc.) in the command
            parts = line.split()
            for part in parts:
                # Check if it looks like a script path
                if any(part.endswith(ext) for ext in ['.csh', '.sh', '.py', '.pl', '.bash']):
                    # Extract just the script name (basename)
                    script_name = os.path.basename(part)
                    processes.add(script_name)
                    break
        
        return processes
    except Exception as e:
        print(f"Error getting running processes: {e}")
        return set()

def load_completed_jobs():
    """Load previously completed jobs from JSON file"""
    global completed_jobs
    
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, 'r') as f:
                data = json.load(f)
                if 'job_runs' in data and 'runs_detail' in data['job_runs']:
                    completed_jobs = data['job_runs']['runs_detail']
                    print(f"Loaded {len(completed_jobs)} previously completed jobs")
    except Exception as e:
        print(f"Error loading completed jobs: {e}")
        completed_jobs = []

def cleanup_old_jobs():
    """Remove job records older than DATA_RETENTION_HOURS"""
    global completed_jobs
    
    cutoff_time = datetime.utcnow() - timedelta(hours=DATA_RETENTION_HOURS)
    cutoff_str = cutoff_time.isoformat()
    
    original_count = len(completed_jobs)
    completed_jobs = [job for job in completed_jobs if job['end'] >= cutoff_str]
    
    removed_count = original_count - len(completed_jobs)
    if removed_count > 0:
        print(f"Cleaned up {removed_count} jobs older than {DATA_RETENTION_HOURS} hours")

def save_completed_jobs():
    """Save completed jobs to JSON file"""
    try:
        # Group by script name for summary
        job_summary = defaultdict(lambda: {
            'total_runs': 0,
            'total_duration_seconds': 0.0,
            'runs_detail': []
        })
        
        for job in completed_jobs:
            script = job['script_name']
            job_summary[script]['total_runs'] += 1
            job_summary[script]['total_duration_seconds'] += job['duration_seconds']
            job_summary[script]['runs_detail'].append(job)
        
        # Convert to final format
        jobs_data = {}
        for script_name, data in job_summary.items():
            jobs_data[script_name] = {
                'total_runs': data['total_runs'],
                'total_duration_seconds': round(data['total_duration_seconds'], 2),
                'avg_duration_seconds': round(data['total_duration_seconds'] / data['total_runs'], 2),
                'runs_detail': sorted(data['runs_detail'], 
                                     key=lambda x: x['start'], 
                                     reverse=True)
            }
        
        # Sort by total duration
        jobs_data = dict(sorted(jobs_data.items(),
                               key=lambda x: x[1]['total_duration_seconds'],
                               reverse=True))
        
        # Create output structure
        output = {
            'metadata': {
                'generator': 'dashboard_login_jobs.py',
                'version': '1.0',
                'generated_at': int(time.time()),
                'generated_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
                'description': f'{DATA_RETENTION_HOURS}-hour login node cron job tracking',
                'data_retention_hours': DATA_RETENTION_HOURS
            },
            'job_runs': {
                'summary': {
                    'total_unique_scripts': len(jobs_data),
                    'total_job_runs': len(completed_jobs),
                    'total_duration_seconds': round(sum(j['duration_seconds'] for j in completed_jobs), 2)
                },
                'jobs': jobs_data,
                'runs_detail': sorted(completed_jobs, 
                                     key=lambda x: x['start'], 
                                     reverse=True)
            }
        }
        
        # Write atomically with temp file
        temp_file = JSON_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(output, f, indent=2)
        os.rename(temp_file, JSON_FILE)
        
    except Exception as e:
        print(f"Error saving completed jobs: {e}")

def monitor_loop():
    """Main monitoring loop"""
    global running_jobs, completed_jobs
    
    # Get the list of login cron scripts to monitor
    login_scripts = get_login_cron_scripts()
    print(f"\nMonitoring {len(login_scripts)} login node cron scripts:")
    for script in sorted(login_scripts):
        print(f"  - {script}")
    print()
    
    iteration = 0
    while not should_exit:
        iteration += 1
        
        # Get currently running processes
        current_processes = get_running_processes()
        
        # Check for newly started jobs
        for script in login_scripts:
            if script in current_processes and script not in running_jobs:
                # New job started
                start_time = datetime.utcnow()
                running_jobs[script] = start_time
                print(f"[{start_time.strftime('%H:%M:%S')}] Started: {script}")
        
        # Check for completed jobs
        for script in list(running_jobs.keys()):
            if script not in current_processes:
                # Job completed
                end_time = datetime.utcnow()
                start_time = running_jobs[script]
                duration = (end_time - start_time).total_seconds()
                
                # Record completed job
                job_record = {
                    'script_name': script,
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'duration_seconds': round(duration, 2)
                }
                completed_jobs.append(job_record)
                
                print(f"[{end_time.strftime('%H:%M:%S')}] Completed: {script} (duration: {duration:.2f}s)")
                
                # Remove from running jobs
                del running_jobs[script]
                
                # Save after each completion
                save_completed_jobs()
        
        # Periodic cleanup and save (every 5 minutes)
        if iteration % 300 == 0:
            cleanup_old_jobs()
            save_completed_jobs()
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Status: {len(running_jobs)} running, {len(completed_jobs)} completed in last {DATA_RETENTION_HOURS}h")
        
        # Wait before next check
        time.sleep(CHECK_INTERVAL)

def acquire_lock():
    """Acquire lock file to prevent multiple instances"""
    try:
        # Check if lock file exists and is stale
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())
                # Check if process is still running
                try:
                    os.kill(old_pid, 0)
                    print(f"Error: Another instance is already running (PID {old_pid})")
                    return False
                except OSError:
                    # Process doesn't exist, remove stale lock
                    print(f"Removing stale lock file from PID {old_pid}")
                    os.remove(LOCK_FILE)
            except:
                os.remove(LOCK_FILE)
        
        # Create lock file with current PID
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        print(f"Error acquiring lock: {e}")
        return False

def release_lock():
    """Release lock file"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        print(f"Error releasing lock: {e}")

def main():
    """Main entry point"""
    
    print("EarthCast HPC Dashboard - Login Node Job Tracker")
    print("=" * 60)
    
    # Check for lock
    if not acquire_lock():
        sys.exit(1)
    
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Load existing completed jobs
        load_completed_jobs()
        
        # Clean up old jobs
        cleanup_old_jobs()
        
        # Start monitoring
        print(f"Starting monitoring (check interval: {CHECK_INTERVAL}s, retention: {DATA_RETENTION_HOURS}h)")
        print(f"JSON output: {JSON_FILE}")
        print(f"Press Ctrl+C to stop\n")
        
        monitor_loop()
        
    finally:
        # Save any running jobs as completed (with current time as end)
        print("\nSaving final state...")
        if running_jobs:
            end_time = datetime.utcnow()
            for script, start_time in running_jobs.items():
                duration = (end_time - start_time).total_seconds()
                job_record = {
                    'script_name': script,
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat(),
                    'duration_seconds': round(duration, 2)
                }
                completed_jobs.append(job_record)
        
        save_completed_jobs()
        release_lock()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
