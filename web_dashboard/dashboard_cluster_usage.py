#!/usr/bin/env python3
"""
EarthCast HPC Dashboard - Cluster Usage Data Generator
Generates cluster job usage analysis data (last 48 hours)
"""

import subprocess
import json
import csv
import time
from datetime import datetime
from collections import defaultdict

def get_job_usage_data():
    """Get and summarize job usage data from last 48 hours"""
    try:
        # Get CSV data from /usr/login/bin/myusage command
        output = subprocess.check_output(['/usr/login/bin/myusage', '--start', 'now-48h', '--count', '2000', '--csv'], 
                                       stderr=subprocess.DEVNULL).decode()
        
        # Skip header lines and get to CSV data
        lines = output.strip().split('\n')
        csv_start = -1
        for i, line in enumerate(lines):
            if line.startswith('id,job_name,user,start,end,cluster,job_state,cores,core_hours'):
                csv_start = i
                break
        
        if csv_start == -1:
            return {
                'error': 'Could not find CSV header in /usr/login/bin/myusage output',
                'jobs': {},
                'summary': {'total_jobs': 0, 'total_core_hours': 0}
            }
        
        # Parse CSV data
        csv_data = '\n'.join(lines[csv_start:])
        csv_reader = csv.DictReader(csv_data.splitlines())
        
        # Group data by job_name
        job_summary = defaultdict(lambda: {
            'clusters': set(),
            'runs': [],
            'total_core_hours': 0.0,
            'total_runs': 0
        })
        
        total_jobs = 0
        total_core_hours = 0.0
        
        for row in csv_reader:
            if not row.get('job_name') or not row.get('cluster'):
                continue
                
            job_name = row['job_name']
            cluster = row['cluster']
            cores = int(row.get('cores', 0))
            core_hours = float(row.get('core_hours', 0.0))
            
            # Add to job summary
            job_summary[job_name]['clusters'].add(cluster)
            job_summary[job_name]['runs'].append({
                'cluster': cluster,
                'cores': cores,
                'core_hours': core_hours,
                'start': row.get('start', ''),
                'end': row.get('end', ''),
                'job_state': row.get('job_state', '')
            })
            job_summary[job_name]['total_core_hours'] += core_hours
            job_summary[job_name]['total_runs'] += 1
            
            total_jobs += 1
            total_core_hours += core_hours
        
        # Convert to final format
        jobs_data = {}
        for job_name, data in job_summary.items():
            jobs_data[job_name] = {
                'clusters': sorted(list(data['clusters'])),
                'total_runs': data['total_runs'],
                'total_core_hours': round(data['total_core_hours'], 4),
                'runs_detail': data['runs']
            }
        
        # Sort jobs by total core hours (descending)
        jobs_data = dict(sorted(jobs_data.items(), 
                               key=lambda x: x[1]['total_core_hours'], 
                               reverse=True))
        
        return {
            'jobs': jobs_data,
            'summary': {
                'total_unique_jobs': len(jobs_data),
                'total_job_runs': total_jobs,
                'total_core_hours': round(total_core_hours, 4),
                'collection_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        }
        
    except Exception as e:
        return {
            'error': f"Error collecting job usage data: {str(e)}",
            'jobs': {},
            'summary': {'total_jobs': 0, 'total_core_hours': 0}
        }

def main():
    """Generate cluster usage dashboard data"""
    
    print("Collecting cluster job usage data for last 48 hours...")
    
    # Collect cluster usage data
    cluster_usage_data = {
        'metadata': {
            'generator': 'dashboard_cluster_usage.py',
            'version': '1.0',
            'generated_at': int(time.time()),
            'generated_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'data_source': '/usr/login/bin/myusage --start now-48h --count 2000 --csv',
            'description': '48-hour cluster job usage summary by job name'
        },
        'job_usage': get_job_usage_data()
    }
    
    # Write JSON file
    with open('dashboard_cluster_usage.json', 'w') as f:
        json.dump(cluster_usage_data, f, indent=2)
    
    # Print summary
    usage_data = cluster_usage_data['job_usage']
    if 'error' not in usage_data:
        summary = usage_data['summary']
        print(f"Generated cluster usage data at {cluster_usage_data['metadata']['generated_time']}")
        print(f"Summary: {summary['total_unique_jobs']} unique jobs, {summary['total_job_runs']} runs, {summary['total_core_hours']} core-hours")
    else:
        print(f"Error: {usage_data['error']}")
    
    print("JSON file: dashboard_cluster_usage.json")

if __name__ == "__main__":
    main()
