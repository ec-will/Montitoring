#!/usr/bin/env python3
"""
Analyze which cluster jobs can be safely moved to login node.
Shows available capacity and recommends specific jobs to migrate.
Python 3.6 compatible.
"""

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

def load_json_data(json_file_path):
    """Load JSON data from file."""
    try:
        with open(json_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading {}: {}".format(json_file_path, e))
        return None

def analyze_login_capacity(login_data, total_cores=16, threshold=0.8):
    """Analyze available capacity on login node over time."""
    job_runs = login_data.get('job_runs', {})
    runs_detail = job_runs.get('runs_detail', [])
    
    # Create timeline of utilization
    events = []
    for run in runs_detail:
        if not run.get('start') or not run.get('end'):
            continue
        
        try:
            if '.' in run['start']:
                start_time = datetime.strptime(run['start'], '%Y-%m-%dT%H:%M:%S.%f')
            else:
                start_time = datetime.strptime(run['start'], '%Y-%m-%dT%H:%M:%S')
            
            if '.' in run['end']:
                end_time = datetime.strptime(run['end'], '%Y-%m-%dT%H:%M:%S.%f')
            else:
                end_time = datetime.strptime(run['end'], '%Y-%m-%dT%H:%M:%S')
            
            events.append((start_time, 1))
            events.append((end_time, -1))
        except (ValueError, TypeError):
            continue
    
    events.sort(key=lambda x: x[0])
    
    # Calculate available capacity at each point
    threshold_cores = int(total_cores * threshold)
    current_cores = 0
    available_capacity = []
    
    for i, (timestamp, delta) in enumerate(events):
        current_cores += delta
        spare_cores = threshold_cores - current_cores
        available_capacity.append((timestamp, spare_cores, current_cores))
    
    return available_capacity, threshold_cores

def analyze_cluster_jobs(cluster_data, max_cores=16, exclude_patterns=None):
    """Analyze cluster jobs and their characteristics."""
    jobs = cluster_data.get('job_usage', {}).get('jobs', {})
    job_analysis = {}
    
    if exclude_patterns is None:
        exclude_patterns = []
    
    for job_name, job_data in jobs.items():
        # Skip excluded job patterns
        if any(pattern in job_name.lower() for pattern in exclude_patterns):
            continue
        
        runs = []
        for run in job_data.get('runs_detail', []):
            cores = run.get('cores', 0)
            if cores > max_cores:
                continue
            
            if not run.get('start') or not run.get('end'):
                continue
            
            try:
                if 'T' in run['start']:
                    start_time = datetime.strptime(run['start'].replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    start_time = datetime.strptime(run['start'], '%Y-%m-%d %H:%M:%S')
                
                if 'T' in run['end']:
                    end_time = datetime.strptime(run['end'].replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    end_time = datetime.strptime(run['end'], '%Y-%m-%d %H:%M:%S')
                
                duration = (end_time - start_time).total_seconds()
                runs.append({
                    'start': start_time,
                    'end': end_time,
                    'cores': cores,
                    'duration': duration
                })
            except (ValueError, TypeError):
                continue
        
        if runs:
            avg_cores = sum(r['cores'] for r in runs) / len(runs)
            avg_duration = sum(r['duration'] for r in runs) / len(runs)
            total_core_seconds = sum(r['cores'] * r['duration'] for r in runs)
            
            job_analysis[job_name] = {
                'runs': runs,
                'count': len(runs),
                'avg_cores': avg_cores,
                'avg_duration': avg_duration,
                'total_core_seconds': total_core_seconds
            }
    
    return job_analysis

def check_job_fits(job_runs, available_capacity, slowdown_factor=1.0):
    """Check how many runs of a job would fit in available capacity.
    
    Args:
        slowdown_factor: Factor by which jobs run slower on login node (e.g. 1.5 = 50% slower)
    
    Returns:
        fits, conflicts, max_cores_during_conflict
    """
    fits = 0
    conflicts = 0
    max_cores_during_conflict = 0
    
    for run in job_runs:
        cores_needed = run['cores']
        start = run['start']
        end = run['end']
        
        # Adjust end time for slowdown factor
        duration = run['duration']
        adjusted_duration = duration * slowdown_factor
        adjusted_end = start + timedelta(seconds=adjusted_duration)
        
        # Check if capacity is available during this time window
        # Find capacity entries that overlap with this job
        would_fit = True
        conflict_peak = 0
        for cap_time, spare_cores, current_cores in available_capacity:
            if start <= cap_time <= adjusted_end:
                if spare_cores < cores_needed:
                    would_fit = False
                    # Track what the utilization would be if we added this job
                    potential_cores = current_cores + cores_needed
                    conflict_peak = max(conflict_peak, potential_cores)
        
        if would_fit:
            fits += 1
        else:
            conflicts += 1
            max_cores_during_conflict = max(max_cores_during_conflict, conflict_peak)
    
    return fits, conflicts, max_cores_during_conflict

def generate_recommendations(login_data, cluster_data, max_cores=16, total_cores=16, threshold=0.8, 
                            exclude_patterns=None, cluster_cost_per_core_hour=0.12, slowdown_factor=1.0):
    """Generate recommendations for which jobs to migrate.
    
    Args:
        slowdown_factor: Factor by which jobs run slower on login node (default 1.0 = same speed)
    """
    
    if exclude_patterns is None:
        exclude_patterns = ['metgrid']
    
    # Analyze login node capacity
    available_capacity, threshold_cores = analyze_login_capacity(login_data, total_cores, threshold)
    
    if not available_capacity:
        print("No login capacity data available")
        return None
    
    avg_spare_cores = sum(c[1] for c in available_capacity) / len(available_capacity)
    min_spare_cores = min(c[1] for c in available_capacity)
    
    print("Login Node Capacity Analysis:")
    print("  Threshold: {} cores ({}%)".format(threshold_cores, int(threshold * 100)))
    print("  Average spare capacity: {:.1f} cores".format(avg_spare_cores))
    print("  Minimum spare capacity: {} cores".format(min_spare_cores))
    print()
    
    # Analyze cluster jobs (excluding specified patterns)
    job_analysis = analyze_cluster_jobs(cluster_data, max_cores, exclude_patterns)
    
    if not job_analysis:
        print("No suitable cluster jobs found")
        return None
    
    print("Found {} cluster jobs using <= {} cores".format(len(job_analysis), max_cores))
    print()
    
    # Evaluate each job for migration
    recommendations = []
    
    for job_name, job_info in job_analysis.items():
        fits, conflicts, max_conflict_cores = check_job_fits(job_info['runs'], available_capacity, slowdown_factor)
        fit_rate = fits / job_info['count'] if job_info['count'] > 0 else 0
        
        # Calculate cost savings
        total_core_hours = job_info['total_core_seconds'] / 3600
        cluster_cost = total_core_hours * cluster_cost_per_core_hour
        potential_savings = cluster_cost * fit_rate  # Savings for runs that would fit
        
        # Score jobs based on fit rate and resource usage
        # Higher score = better candidate
        score = fit_rate * 100
        
        recommendations.append({
            'job_name': job_name,
            'runs': job_info['count'],
            'avg_cores': job_info['avg_cores'],
            'avg_duration_min': job_info['avg_duration'] / 60,
            'fits': fits,
            'conflicts': conflicts,
            'fit_rate': fit_rate,
            'max_conflict_cores': max_conflict_cores,
            'score': score,
            'total_core_hours': total_core_hours,
            'cluster_cost': cluster_cost,
            'potential_savings': potential_savings
        })
    
    # Sort by score (best candidates first)
    recommendations.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        'spare_capacity': {
            'threshold_cores': threshold_cores,
            'avg_spare': avg_spare_cores,
            'min_spare': min_spare_cores
        },
        'recommendations': recommendations
    }

def print_recommendations(results):
    """Print recommendations in a readable format."""
    
    if not results:
        return
    
    print("=" * 100)
    print("JOB MIGRATION RECOMMENDATIONS")
    print("=" * 100)
    print()
    
    print("BEST CANDIDATES (jobs that would usually fit):")
    print("-" * 120)
    print("{:<35} {:>6} {:>7} {:>9} {:>8} {:>10} {:>7} {:>10} {:>10}".format(
        "Job Name", "Runs", "Cores", "Duration", "Fits", "Conflicts", "Fit %", "Peak", "Savings"
    ))
    print("-" * 120)
    
    good_candidates = [r for r in results['recommendations'] if r['fit_rate'] >= 0.8]
    total_good_savings = sum(r['potential_savings'] for r in good_candidates)
    
    for rec in good_candidates[:20]:  # Top 20
        peak_str = "{}c".format(rec['max_conflict_cores']) if rec['conflicts'] > 0 else "-"
        print("{:<35} {:>6} {:>7.1f} {:>8.1f}m {:>8} {:>10} {:>6.0f}% {:>10} {:>9.2f}".format(
            rec['job_name'][:35],
            rec['runs'],
            rec['avg_cores'],
            rec['avg_duration_min'],
            rec['fits'],
            rec['conflicts'],
            rec['fit_rate'] * 100,
            peak_str,
            rec['potential_savings']
        ))
    
    print()
    print("MAYBE CANDIDATES (jobs that sometimes fit):")
    print("-" * 100)
    
    maybe_candidates = [r for r in results['recommendations'] if 0.3 <= r['fit_rate'] < 0.8]
    for rec in maybe_candidates[:10]:  # Top 10
        print("{:<40} {:>6} {:>8.1f} {:>9.1f}m {:>8} {:>10} {:>7.0f}%".format(
            rec['job_name'][:40],
            rec['runs'],
            rec['avg_cores'],
            rec['avg_duration_min'],
            rec['fits'],
            rec['conflicts'],
            rec['fit_rate'] * 100
        ))
    
    print()
    print("POOR CANDIDATES (jobs that rarely fit):")
    print("-" * 100)
    
    poor_candidates = [r for r in results['recommendations'] if r['fit_rate'] < 0.3]
    for rec in poor_candidates[:5]:  # Just show a few
        print("{:<40} {:>6} {:>8.1f} {:>9.1f}m {:>8} {:>10} {:>7.0f}%".format(
            rec['job_name'][:40],
            rec['runs'],
            rec['avg_cores'],
            rec['avg_duration_min'],
            rec['fits'],
            rec['conflicts'],
            rec['fit_rate'] * 100
        ))
    
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("  Good candidates (>=80% fit): {}".format(len(good_candidates)))
    print("  Maybe candidates (30-80% fit): {}".format(len(maybe_candidates)))
    print("  Poor candidates (<30% fit): {}".format(len(poor_candidates)))
    print()
    print("COST SAVINGS (48-hour period, extrapolated monthly):")
    total_good_savings = sum(r['potential_savings'] for r in good_candidates)
    total_maybe_savings = sum(r['potential_savings'] for r in maybe_candidates)
    print("  Good candidates: ${:.2f} (48h) = ${:.2f}/month".format(
        total_good_savings, total_good_savings * 15.2))
    print("  Maybe candidates: ${:.2f} (48h) = ${:.2f}/month".format(
        total_maybe_savings, total_maybe_savings * 15.2))
    print("  TOTAL POTENTIAL: ${:.2f} (48h) = ${:.2f}/month".format(
        total_good_savings + total_maybe_savings, (total_good_savings + total_maybe_savings) * 15.2))
    print("=" * 100)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 analyze_job_migration.py <login_json> <cluster_json> [max_cluster_cores] [total_login_cores] [threshold] [slowdown_factor]")
        print("Example: python3 analyze_job_migration.py dashboard_login_jobs.json dashboard_cluster_usage.json 16 16 0.8 1.5")
        sys.exit(1)
    
    login_json = sys.argv[1]
    cluster_json = sys.argv[2]
    max_cluster_cores = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    total_login_cores = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    threshold = float(sys.argv[5]) if len(sys.argv) > 5 else 0.8
    slowdown_factor = float(sys.argv[6]) if len(sys.argv) > 6 else 1.0
    
    login_data = load_json_data(login_json)
    cluster_data = load_json_data(cluster_json)
    
    if not login_data or not cluster_data:
        print("Error loading data files")
        sys.exit(1)
    
    results = generate_recommendations(login_data, cluster_data, max_cluster_cores, total_login_cores, threshold, 
                                      None, 0.12, slowdown_factor)
    
    if results:
        print_recommendations(results)
