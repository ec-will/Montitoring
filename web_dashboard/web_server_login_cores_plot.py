#!/usr/bin/env python3
"""
Generate login node core utilization timeline plot.
Shows how many of the 16 login node cores are in use over time.
Python 3.6 compatible.
"""

import json
import sys
from datetime import datetime, timedelta

def load_login_jobs_data(json_file_path):
    """Load login jobs data from JSON file."""
    try:
        with open(json_file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading {}: {}".format(json_file_path, e))
        return None

def calculate_core_utilization_from_runs(runs_detail):
    """
    Calculate core utilization over time from runs_detail list.
    Returns list of (timestamp, cores_used) tuples.
    """
    # Collect all time events (job starts and ends)
    events = []
    
    for run in runs_detail:
        if not run.get('start') or not run.get('end'):
            continue
        
        try:
            # Parse timestamps
            start_str = run['start']
            end_str = run['end']
            script = run.get('script', 'unknown')
            
            if '.' in start_str:
                start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
            
            if '.' in end_str:
                end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S.%f')
            else:
                end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
            
            # Add start event (+1 core) and end event (-1 core)
            events.append((start_time, 1, script))
            events.append((end_time, -1, script))
            
        except (ValueError, TypeError) as e:
            continue
    
    # Sort events by time
    events.sort(key=lambda x: x[0])
    
    # Calculate running core count at each event
    timeline = []
    current_cores = 0
    
    for timestamp, delta, script in events:
        current_cores += delta
        timeline.append((timestamp, current_cores))
    
    return timeline

def generate_plotly_html(timeline, metadata, total_cores=16):
    """Generate interactive Plotly HTML showing core utilization over time."""
    
    if not timeline:
        return "<html><body><h2>No data available</h2></body></html>"
    
    # Prepare data for Plotly - create area fill
    timestamps = [t[0].strftime('%Y-%m-%d %H:%M:%S') for t in timeline]
    cores_used = [t[1] for t in timeline]
    
    # Calculate statistics
    max_cores = max(cores_used) if cores_used else 0
    avg_cores = sum(cores_used) / len(cores_used) if cores_used else 0
    
    # Calculate time above 80% threshold (12.8 cores, round to 13)
    threshold = int(total_cores * 0.8)
    time_above_threshold = 0
    for i in range(len(timeline) - 1):
        if cores_used[i] >= threshold:
            duration = (timeline[i+1][0] - timeline[i][0]).total_seconds()
            time_above_threshold += duration
    time_above_threshold_hours = time_above_threshold / 3600
    
    # Create HTML with embedded Plotly (minimal styling - will be embedded in index.html)
    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Login Node Core Utilization</title>
    <script src="https://cdn.plot.ly/plotly-2.25.2.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        #plotDiv {{ background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <div id="plotDiv"></div>

    <script>
        var timestamps = {timestamps_json};
        var coresUsed = {cores_used_json};
        
        // Create area trace for core utilization
        var utilizationArea = {{
            x: timestamps,
            y: coresUsed,
            fill: 'tozeroy',
            type: 'scatter',
            mode: 'none',
            name: 'Cores Used',
            fillcolor: 'rgba(33, 150, 243, 0.5)',
            hovertemplate: 'Time: %{{x}}<br>Cores Used: %{{y}}/{total_cores}<br><extra></extra>'
        }};
        
        // Add threshold line at 80% ({threshold} cores)
        var thresholdTrace = {{
            x: [timestamps[0], timestamps[timestamps.length - 1]],
            y: [{threshold}, {threshold}],
            type: 'scatter',
            mode: 'lines',
            name: '80% Threshold',
            line: {{
                color: '#FF9800',
                width: 2,
                dash: 'dash'
            }},
            hovertemplate: '80% Threshold: {threshold} cores<extra></extra>'
        }};
        
        // Add max capacity line
        var maxCapacityTrace = {{
            x: [timestamps[0], timestamps[timestamps.length - 1]],
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
        
        var data = [utilizationArea, thresholdTrace, maxCapacityTrace];
        
        var layout = {{
            title: {{
                text: 'Login Node Core Utilization (48-hour window)',
                x: 0.5,
                xanchor: 'center'
            }},
            xaxis: {{
                title: 'Time',
                gridcolor: '#e0e0e0',
                gridwidth: 1,
                showgrid: true,
                zeroline: false,
                linecolor: '#333333',
                linewidth: 2,
                type: 'date'
            }},
            yaxis: {{
                title: 'Cores Used',
                range: [0, {total_cores_plus_1}],
                gridcolor: '#e0e0e0',
                gridwidth: 1,
                showgrid: true,
                zeroline: true,
                linecolor: '#333333',
                linewidth: 2,
                dtick: 2
            }},
            hovermode: 'x unified',
            height: 500,
            width: 1200,
            margin: {{l: 80, r: 50, t: 80, b: 80}},
            plot_bgcolor: '#f9f9f9',
            paper_bgcolor: 'white',
            showlegend: true,
            legend: {{
                x: 1,
                xanchor: 'right',
                y: 1,
                yanchor: 'top',
                bgcolor: 'rgba(255, 255, 255, 0.8)',
                bordercolor: '#ddd',
                borderwidth: 1
            }},
            annotations: [
                {{
                    text: 'Peak: {max_cores} cores | Avg: {avg_cores:.1f} cores | Time >80%: {time_above_threshold_hours:.1f}h',
                    xref: 'paper',
                    yref: 'paper',
                    x: 0.5,
                    y: -0.15,
                    xanchor: 'center',
                    yanchor: 'top',
                    showarrow: false,
                    font: {{
                        size: 12,
                        color: '#666'
                    }}
                }}
            ]
        }};
        
        Plotly.newPlot('plotDiv', data, layout, {{responsive: true}});
    </script>
</body>
</html>'''.format(
        timestamps_json=json.dumps(timestamps),
        cores_used_json=json.dumps(cores_used),
        total_cores=total_cores,
        total_cores_plus_1=total_cores + 1,
        threshold=threshold,
        max_cores=max_cores,
        avg_cores=avg_cores,
        time_above_threshold_hours=time_above_threshold_hours
    )
    
    return html_content

def generate_core_utilization_plot(json_file_path, output_file_path, total_cores=16):
    """Generate interactive core utilization plot from login jobs data."""
    
    # Load data
    data = load_login_jobs_data(json_file_path)
    
    if not data:
        return False
    
    job_runs = data.get('job_runs', {})
    metadata = data.get('metadata', {})
    runs_detail = job_runs.get('runs_detail', [])
    
    if not runs_detail:
        print("No job run data found")
        return False
    
    # Calculate core utilization timeline
    timeline = calculate_core_utilization_from_runs(runs_detail)
    
    if not timeline:
        print("No timeline data generated")
        return False
    
    # Generate HTML
    html_content = generate_plotly_html(timeline, metadata, total_cores)
    
    # Write to file
    with open(output_file_path, 'w') as f:
        f.write(html_content)
    
    # Calculate statistics
    cores_used = [t[1] for t in timeline]
    max_cores = max(cores_used)
    avg_cores = sum(cores_used) / len(cores_used)
    
    print("Generated {}".format(output_file_path))
    print("Data from: {}".format(metadata.get('generated_time', 'Unknown')))
    print("Timeline points: {}".format(len(timeline)))
    print("Peak cores: {}/{}".format(max_cores, total_cores))
    print("Average cores: {:.1f}/{}".format(avg_cores, total_cores))
    
    return True

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 web_server_login_cores_plot.py <input_json> <output_html> [total_cores]")
        print("Example: python3 web_server_login_cores_plot.py dashboard_login_jobs.json login_cores_utilization.html 16")
        sys.exit(1)
    
    json_file = sys.argv[1]
    output_file = sys.argv[2]
    total_cores = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    
    success = generate_core_utilization_plot(json_file, output_file, total_cores)
    sys.exit(0 if success else 1)
