#!/usr/bin/env python3
"""
Generate combined login node core utilization plot.
Shows actual login node jobs + simulated small cluster jobs (<=16 cores).
Python 3.6 compatible.
"""

import json
import sys
from datetime import datetime, timedelta

def load_json_data(json_file_path):
    """Load JSON data from file."""
    try:
        with open(json_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading {}: {}".format(json_file_path, e))
        return None

def calculate_utilization_from_events(events):
    """
    Calculate core utilization over time from events list.
    Events format: [(timestamp, delta_cores, job_type), ...]
    Returns list of (timestamp, cores_used) tuples.
    """
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    # Calculate running core count at each event
    timeline = []
    current_cores = 0
    
    for timestamp, delta, job_type in events:
        current_cores += delta
        timeline.append((timestamp, current_cores))
    
    return timeline

def extract_login_job_events(login_data):
    """Extract events from login jobs data."""
    events = []
    
    job_runs = login_data.get('job_runs', {})
    runs_detail = job_runs.get('runs_detail', [])
    
    for run in runs_detail:
        if not run.get('start') or not run.get('end'):
            continue
        
        try:
            start_str = run['start']
            end_str = run['end']
            script_name = run.get('script', 'unknown')
            
            if '.' in start_str:
                start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
            
            if '.' in end_str:
                end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
            
            # Each login job uses 1 core
            events.append((start_time, 1, script_name))
            events.append((end_time, -1, script_name))
            
        except (ValueError, TypeError):
            continue
    
    return events

def extract_cluster_job_events(cluster_data, max_cores=16):
    """Extract events from cluster jobs data for jobs using <= max_cores."""
    events = []
    
    jobs = cluster_data.get('job_usage', {}).get('jobs', {})
    
    for job_name, job_data in jobs.items():
        for run in job_data.get('runs_detail', []):
            if not run.get('start') or not run.get('end'):
                continue
            
            cores = run.get('cores', 0)
            if cores > max_cores:
                continue  # Skip jobs using more than max_cores
            
            try:
                start_str = run['start']
                end_str = run['end']
                
                if 'T' in start_str:
                    start_time = datetime.strptime(start_str.replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                
                if 'T' in end_str:
                    end_time = datetime.strptime(end_str.replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    end_time = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
                
                # Add events for this job's core usage with job name and core count
                events.append((start_time, cores, '{}({})'.format(job_name, cores)))
                events.append((end_time, -cores, '{}({})'.format(job_name, cores)))
                
            except (ValueError, TypeError):
                continue
    
    return events

def generate_combined_timeline(login_events, cluster_events):
    """
    Generate separate timelines for login and cluster jobs.
    Returns (login_timeline, cluster_timeline) tuples.
    """
    # For timeline generation, we just need timestamp, delta, and a dummy type
    # Events already have job names in position 2, so just pass them through
    login_timeline = calculate_utilization_from_events(
        [(t, d, 'login') for t, d, job_name in login_events]
    )
    
    cluster_timeline = calculate_utilization_from_events(
        [(t, d, 'cluster') for t, d, job_name in cluster_events]
    )
    
    return login_timeline, cluster_timeline

def find_high_utilization_periods(login_events, cluster_events, threshold_cores=13):
    """Find periods where total utilization exceeds threshold and list running jobs."""
    # Combine all events and sort by time
    all_events = []
    
    # Track which jobs are running
    for timestamp, delta, job_name in login_events:
        all_events.append((timestamp, delta, job_name, 'login'))
    
    for timestamp, delta, job_name in cluster_events:
        all_events.append((timestamp, delta, job_name, 'cluster'))
    
    all_events.sort(key=lambda x: x[0])
    
    # Track running jobs and utilization
    running_login_jobs = set()
    running_cluster_jobs = {}
    current_login_cores = 0
    current_cluster_cores = 0
    high_util_periods = []
    in_high_util = False
    period_start = None
    period_max_cores = 0
    
    for timestamp, delta, job_name, source in all_events:
        # Update running jobs and core counts
        if source == 'login':
            if delta > 0:  # Job started
                running_login_jobs.add(job_name)
                current_login_cores += 1
            else:  # Job ended
                running_login_jobs.discard(job_name)
                current_login_cores -= 1
        else:  # cluster
            if delta > 0:  # Job started
                running_cluster_jobs[job_name] = abs(delta)
                current_cluster_cores += abs(delta)
            else:  # Job ended
                if job_name in running_cluster_jobs:
                    current_cluster_cores -= running_cluster_jobs[job_name]
                    del running_cluster_jobs[job_name]
        
        total_cores = current_login_cores + current_cluster_cores
        
        # Track max cores during high utilization period
        if in_high_util:
            period_max_cores = max(period_max_cores, total_cores)
        
        # Check if we crossed threshold
        if total_cores >= threshold_cores and not in_high_util:
            in_high_util = True
            period_start = timestamp
            period_max_cores = total_cores
        elif total_cores < threshold_cores and in_high_util:
            in_high_util = False
            if period_start:
                high_util_periods.append({
                    'start': period_start,
                    'end': timestamp,
                    'login_jobs': list(running_login_jobs.copy()),
                    'cluster_jobs': list(running_cluster_jobs.keys()),
                    'max_cores': period_max_cores
                })
    
    # Handle case where we're still in high utilization at end
    if in_high_util and period_start:
        high_util_periods.append({
            'start': period_start,
            'end': all_events[-1][0] if all_events else period_start,
            'login_jobs': list(running_login_jobs.copy()),
            'cluster_jobs': list(running_cluster_jobs.keys()),
            'max_cores': period_max_cores
        })
    
    return high_util_periods

def generate_plotly_html(login_timeline, cluster_timeline, metadata, total_cores=16, high_util_periods=None):
    """Generate interactive Plotly HTML with stacked area charts."""
    
    if not login_timeline and not cluster_timeline:
        return "<html><body><h2>No data available</h2></body></html>"
    
    # Prepare login data
    login_timestamps = [t[0].strftime('%Y-%m-%d %H:%M:%S') for t in login_timeline] if login_timeline else []
    login_cores = [t[1] for t in login_timeline] if login_timeline else []
    
    # Prepare cluster data  
    cluster_timestamps = [t[0].strftime('%Y-%m-%d %H:%M:%S') for t in cluster_timeline] if cluster_timeline else []
    cluster_cores = [t[1] for t in cluster_timeline] if cluster_timeline else []
    
    # Calculate stats
    max_login = max(login_cores) if login_cores else 0
    max_cluster = max(cluster_cores) if cluster_cores else 0
    avg_login = sum(login_cores) / len(login_cores) if login_cores else 0
    avg_cluster = sum(cluster_cores) / len(cluster_cores) if cluster_cores else 0
    
    # Calculate max combined usage from high_util_periods if available
    max_combined = total_cores
    if high_util_periods and len(high_util_periods) > 0:
        max_combined = max([p['max_cores'] for p in high_util_periods])
    
    # Set y-axis max to at least show the maximum combined usage
    y_axis_max = max(total_cores + 2, max_combined + 2)
    
    threshold = int(total_cores * 0.8)
    
    # Generate high utilization table HTML
    high_util_table_html = ''
    if high_util_periods and len(high_util_periods) > 0:
        # Sort by max cores descending
        sorted_periods = sorted(high_util_periods, key=lambda x: x['max_cores'], reverse=True)
        
        high_util_table_html = '<table><thead><tr><th>Start Time</th><th>End Time</th><th>Duration</th><th>Max Cores</th><th>Login Jobs</th><th>Cluster Jobs</th></tr></thead><tbody>'
        for period in sorted_periods:
            duration = (period['end'] - period['start']).total_seconds() / 60
            start_str = period['start'].strftime('%Y-%m-%d %H:%M:%S')
            end_str = period['end'].strftime('%Y-%m-%d %H:%M:%S')
            
            login_jobs_html = '<br>'.join(['<span class="login-job">{}</span>'.format(j) for j in period['login_jobs']]) if period['login_jobs'] else '-'
            cluster_jobs_html = '<br>'.join(['<span class="cluster-job">{}</span>'.format(j) for j in period['cluster_jobs']]) if period['cluster_jobs'] else '-'
            
            high_util_table_html += '<tr>'
            high_util_table_html += '<td>{}</td>'.format(start_str)
            high_util_table_html += '<td>{}</td>'.format(end_str)
            high_util_table_html += '<td>{:.1f} min</td>'.format(duration)
            high_util_table_html += '<td>{}</td>'.format(period['max_cores'])
            high_util_table_html += '<td>{}</td>'.format(login_jobs_html)
            high_util_table_html += '<td>{}</td>'.format(cluster_jobs_html)
            high_util_table_html += '</tr>'
        high_util_table_html += '</tbody></table>'
    else:
        high_util_table_html = '<p>No periods found where utilization exceeded 80% (13 cores)</p>'
    
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Login Node Core Utilization - Actual + Simulated</title>
    <script src="https://cdn.plot.ly/plotly-2.25.2.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #000000; color: #ffffff; }}
        #plotDiv {{ background-color: #000000; border-radius: 8px; box-shadow: 0 2px 8px rgba(255,255,255,0.1); }}
        #highUtilTable {{ margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; background-color: #1a1a1a; }}
        th, td {{ padding: 10px; text-align: left; border: 1px solid #444; }}
        th {{ background-color: #2a2a2a; font-weight: bold; }}
        tr:hover {{ background-color: #2a2a2a; }}
        .login-job {{ color: #999999; }}
        .cluster-job {{ color: #ffffff; font-weight: bold; }}
        h2 {{ color: #ffffff; margin-top: 30px; }}
    </style>
</head>
<body>
    <div id="plotDiv"></div>

    <script>
        var loginTimestamps = {login_timestamps_json};
        var loginCores = {login_cores_json};
        var clusterTimestamps = {cluster_timestamps_json};
        var clusterCores = {cluster_cores_json};
        
        // Actual login node jobs (60% white)
        var loginTrace = {{
            x: loginTimestamps,
            y: loginCores,
            fill: 'tozeroy',
            type: 'scatter',
            mode: 'none',
            name: 'Login Jobs (Actual)',
            fillcolor: 'rgba(153, 153, 153, 0.8)',
            stackgroup: 'one',
            hovertemplate: 'Time: %{{x}}<br>Login Jobs: %{{y}} cores<br><extra></extra>'
        }};
        
        // Simulated small cluster jobs (100% white)
        var clusterTrace = {{
            x: clusterTimestamps,
            y: clusterCores,
            fill: 'tonexty',
            type: 'scatter',
            mode: 'none',
            name: 'Cluster Jobs ≤16 cores (Simulated)',
            fillcolor: 'rgba(255, 255, 255, 1.0)',
            stackgroup: 'one',
            hovertemplate: 'Time: %{{x}}<br>Cluster Jobs: %{{y}} cores<br><extra></extra>'
        }};
        
        // Threshold line
        var thresholdTrace = {{
            x: [loginTimestamps[0] || clusterTimestamps[0], 
                loginTimestamps[loginTimestamps.length - 1] || clusterTimestamps[clusterTimestamps.length - 1]],
            y: [{threshold}, {threshold}],
            type: 'scatter',
            mode: 'lines',
            name: '80% Threshold',
            line: {{
                color: '#FF5722',
                width: 2,
                dash: 'dash'
            }},
            hovertemplate: '80% Threshold: {threshold} cores<extra></extra>'
        }};
        
        // Max capacity line
        var maxCapacityTrace = {{
            x: [loginTimestamps[0] || clusterTimestamps[0],
                loginTimestamps[loginTimestamps.length - 1] || clusterTimestamps[clusterTimestamps.length - 1]],
            y: [{total_cores}, {total_cores}],
            type: 'scatter',
            mode: 'lines',
            name: 'Max Capacity',
            line: {{
                color: '#F44336',
                width: 2,
                dash: 'dot'
            }},
            hovertemplate: 'Max Capacity: {total_cores} cores<extra></extra>'
        }};
        
        var data = [loginTrace, clusterTrace, thresholdTrace, maxCapacityTrace];
        
        var layout = {{
            title: {{
                text: 'Login Node Capacity Analysis: Actual + Simulated Small Cluster Jobs',
                x: 0.5,
                xanchor: 'center',
                font: {{color: '#ffffff'}}
            }},
            xaxis: {{
                title: 'Time',
                titlefont: {{color: '#ffffff'}},
                tickfont: {{color: '#ffffff'}},
                gridcolor: '#444444',
                gridwidth: 1,
                showgrid: true,
                zeroline: false,
                linecolor: '#888888',
                linewidth: 2,
                type: 'date'
            }},
            yaxis: {{
                title: 'Cores Used',
                titlefont: {{color: '#ffffff'}},
                tickfont: {{color: '#ffffff'}},
                range: [0, {y_axis_max}],
                gridcolor: '#444444',
                gridwidth: 1,
                showgrid: true,
                zeroline: true,
                linecolor: '#888888',
                linewidth: 2,
                dtick: 2
            }},
            hovermode: 'x unified',
            height: 600,
            width: 1600,
            margin: {{l: 80, r: 50, t: 100, b: 100}},
            plot_bgcolor: '#000000',
            paper_bgcolor: '#000000',
            showlegend: true,
            legend: {{
                x: 0.02,
                xanchor: 'left',
                y: 0.98,
                yanchor: 'top',
                bgcolor: 'rgba(0, 0, 0, 0.8)',
                bordercolor: '#888',
                borderwidth: 1,
                font: {{color: '#ffffff'}}
            }},
            annotations: [
                {{
                    text: 'Login: Peak {max_login} cores, Avg {avg_login:.1f} | Cluster ≤16: Peak {max_cluster} cores, Avg {avg_cluster:.1f}',
                    xref: 'paper',
                    yref: 'paper',
                    x: 0.5,
                    y: -0.12,
                    xanchor: 'center',
                    yanchor: 'top',
                    showarrow: false,
                    font: {{
                        size: 12,
                        color: '#ffffff'
                    }}
                }}
            ]
        }};
        
        Plotly.newPlot('plotDiv', data, layout, {{responsive: true}});
    </script>
    
    <div id="highUtilTable">
        <h2>High Utilization Periods (>80% = 13+ cores)</h2>
        {high_util_table_html}
    </div>
</body>
</html>'''.format(
        login_timestamps_json=json.dumps(login_timestamps),
        login_cores_json=json.dumps(login_cores),
        cluster_timestamps_json=json.dumps(cluster_timestamps),
        cluster_cores_json=json.dumps(cluster_cores),
        total_cores=total_cores,
        total_cores_plus_2=total_cores + 2,
        threshold=threshold,
        max_login=max_login,
        avg_login=avg_login,
        max_cluster=max_cluster,
        avg_cluster=avg_cluster,
        high_util_table_html=high_util_table_html,
        y_axis_max=y_axis_max
    )
    
    return html_content

def generate_combined_plot(login_json, cluster_json, output_file, max_cluster_cores=16, total_cores=16):
    """Generate combined utilization plot."""
    
    # Load both data files
    login_data = load_json_data(login_json)
    cluster_data = load_json_data(cluster_json)
    
    if not login_data and not cluster_data:
        print("Error: Could not load either data file")
        return False
    
    # Extract events
    login_events = extract_login_job_events(login_data) if login_data else []
    cluster_events = extract_cluster_job_events(cluster_data, max_cluster_cores) if cluster_data else []
    
    # Find earliest login job time to filter cluster events
    if login_events:
        earliest_login_time = min([t for t, d, jt in login_events])
        print("Filtering cluster events to start from: {}".format(earliest_login_time))
        
        # Filter cluster events to only include those after earliest login time
        cluster_events = [(t, d, jt) for t, d, jt in cluster_events if t >= earliest_login_time]
    
    print("Extracted {} login job events".format(len(login_events)))
    print("Extracted {} cluster job events (≤{} cores)".format(len(cluster_events), max_cluster_cores))
    
    # Generate timelines
    login_timeline, cluster_timeline = generate_combined_timeline(login_events, cluster_events)
    
    if not login_timeline and not cluster_timeline:
        print("No timeline data generated")
        return False
    
    # Find high utilization periods
    threshold_cores = int(total_cores * 0.8)
    high_util_periods = find_high_utilization_periods(login_events, cluster_events, threshold_cores)
    print("Found {} high utilization periods (>{}cores)".format(len(high_util_periods), threshold_cores))
    
    # Generate HTML
    metadata = login_data.get('metadata', {}) if login_data else {}
    html_content = generate_plotly_html(login_timeline, cluster_timeline, metadata, total_cores, high_util_periods)
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print("Generated {}".format(output_file))
    return True

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python3 web_server_combined_cores_plot.py <login_json> <cluster_json> <output_html> [max_cluster_cores] [total_cores]")
        print("Example: python3 web_server_combined_cores_plot.py dashboard_login_jobs.json dashboard_cluster_usage.json combined_cores.html 16 16")
        sys.exit(1)
    
    login_json = sys.argv[1]
    cluster_json = sys.argv[2]
    output_file = sys.argv[3]
    max_cluster_cores = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    total_cores = int(sys.argv[5]) if len(sys.argv) > 5 else 16
    
    success = generate_combined_plot(login_json, cluster_json, output_file, max_cluster_cores, total_cores)
    sys.exit(0 if success else 1)
