#!/usr/bin/env python3
"""
Web Server Timeline Plot Generator for EarthCast Login Node Jobs
Reads dashboard_login_jobs.json and generates login_jobs_timeline.html
Should be run on the web server after receiving updated JSON data.
"""

import json
import sys
import os
from datetime import datetime, timedelta

def load_job_data(json_file_path):
    """Load job data from JSON file."""
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: {json_file_path} not found")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {json_file_path}")
        return None

def generate_plotly_html(jobs_data, data_metadata, jobs_in_window):
    """Generate the HTML with embedded Plotly timeline visualization."""
    
    # Color palette for different job types
    job_colors = {}
    colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63', '#9C27B0',
              '#00BCD4', '#FF5722', '#607D8B', '#FFC107', '#00E676',
              '#3F51B5', '#FF6F00', '#00C853', '#D500F9', '#FF3D00']
    color_idx = 0
    
    # Set time window: 48 hours ago to now (48 hours total)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=48)
    
    # Calculate statistics for each job for sorting
    job_stats = {}
    for job_name, job_data in jobs_data.items():
        job_stats[job_name] = {
            'total_runs': job_data['total_runs'],
            'avg_duration': job_data['avg_duration_seconds'],
            'total_duration': job_data['total_duration_seconds']
        }
    
    # Sort jobs by total runtime (descending - jobs that take most login node time at top)
    sorted_jobs = sorted(jobs_data.keys(), 
                        key=lambda x: job_stats.get(x, {}).get('total_duration', 0), 
                        reverse=True)
    
    # Prepare plot data
    plot_data = []
    num_jobs = len(sorted_jobs)
    
    for job_idx, job_name in enumerate(sorted_jobs):
        job_data = jobs_data[job_name]
        
        # Get color for this job type (based on prefix or script type)
        job_type = job_name.split('_')[0] if '_' in job_name else job_name[:10]
        if job_type not in job_colors:
            job_colors[job_type] = colors[color_idx % len(colors)]
            color_idx += 1
        
        color = job_colors[job_type]
        
        # Collect bars for this job
        bars = []
        
        for run in job_data['runs_detail']:
            if not run.get('end') or not run.get('start'):
                continue
                
            try:
                # Parse start and end times (ISO format: 2025-11-15T02:36:48.168364)
                start_str = run['start']
                end_str = run['end']
                
                # Handle ISO format with microseconds
                if 'T' in start_str:
                    # Split and parse properly
                    if '.' in start_str:
                        run_start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S.%f')
                    else:
                        run_start_time = datetime.strptime(start_str, '%Y-%m-%dT%H:%M:%S')
                    
                    if '.' in end_str:
                        run_end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S.%f')
                    else:
                        run_end_time = datetime.strptime(end_str, '%Y-%m-%dT%H:%M:%S')
                else:
                    run_start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                    run_end_time = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
                
                # Include all jobs (no time window filter since data is already 48hr window)
                duration_seconds = run['duration_seconds']
                duration_minutes = duration_seconds / 60
                
                # Reverse Y position so longest total duration jobs appear at top
                y_pos = num_jobs - 1 - job_idx
                
                bars.append({
                    'start': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'end': run_end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'y': y_pos,
                    'duration': duration_seconds,
                    'hover': f"Script: {job_name}<br>Start: {start_str}<br>End: {end_str}<br>Duration: {duration_minutes:.2f} min ({duration_seconds:.1f}s)"
                })
                    
            except (ValueError, TypeError) as e:
                continue
        
        if bars:
            plot_data.append({
                'name': job_name,
                'color': color,
                'bars': bars,
                'avg_duration': job_stats.get(job_name, {}).get('avg_duration', 0),
                'total_runs': job_stats.get(job_name, {}).get('total_runs', 0)
            })
    
    # Generate job labels for y-axis with stats - reverse order to match Y positions
    job_labels = []
    for job in reversed(sorted_jobs):
        label = job.replace('.csh', '').replace('.sh', '').replace('_', ' ')
        stats = job_stats.get(job, {})
        runs = stats.get('total_runs', 0)
        avg_dur = stats.get('avg_duration', 0)
        label += f' ({runs}x, ~{avg_dur:.0f}s)'
        job_labels.append(label)
    
    # Create HTML with embedded Plotly (minimal styling - will be embedded in index.html)
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>EarthCast Login Node Job Timeline</title>
    <script src="https://cdn.plot.ly/plotly-2.25.2.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        #plotDiv {{ background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <div id="plotDiv"></div>

    <script>
        var traces = [];
        var plotData = {json.dumps(plot_data)};
        var jobLabels = {json.dumps(job_labels)};
        
        plotData.forEach(function(jobGroup) {{
            if (jobGroup.bars.length > 0) {{
                // Create horizontal bars using scatter with fill
                jobGroup.bars.forEach(function(bar, idx) {{
                    var trace = {{
                        x: [bar.start, bar.end, bar.end, bar.start, bar.start],
                        y: [bar.y - 0.225, bar.y - 0.225, bar.y + 0.225, bar.y + 0.225, bar.y - 0.225],
                        fill: 'toself',
                        fillcolor: jobGroup.color,
                        line: {{
                            color: jobGroup.color,
                            width: 1
                        }},
                        opacity: 0.8,
                        mode: 'lines',
                        name: jobGroup.name,
                        showlegend: false,
                        text: bar.hover,
                        hovertemplate: '%{{text}}<extra></extra>'
                    }};
                    traces.push(trace);
                }});
            }}
        }});

        var layout = {{
            title: {{
                text: 'Login Node Job Timeline (48-hour window)',
                x: 0.5,
                xanchor: 'center'
            }},
            xaxis: {{
                title: 'Time',
                gridcolor: '#333333',
                gridwidth: 1,
                showgrid: true,
                zeroline: false,
                linecolor: '#333333',
                linewidth: 2,
                type: 'date'
            }},
            yaxis: {{
                title: 'Scripts (sorted by total runtime)',
                tickmode: 'array',
                tickvals: Array.from({{length: jobLabels.length}}, (_, i) => i),
                ticktext: jobLabels,
                tickfont: {{size: 9}},
                showgrid: true,
                gridcolor: '#e0e0e0',
                gridwidth: 1,
                zeroline: false,
                linecolor: '#333333',
                linewidth: 2
            }},
            hovermode: 'closest',
            height: Math.max(600, jobLabels.length * 20 + 200),
            width: 1400,
            margin: {{l: 250, r: 50, t: 80, b: 80}},
            plot_bgcolor: '#f0f8ff',
            paper_bgcolor: 'white',
            showlegend: false
        }};

        Plotly.newPlot('plotDiv', traces, layout, {{responsive: true}});
    </script>
</body>
</html>'''
    
    return html_content

def generate_timeline_plot(json_file_path, output_file_path):
    """Generate interactive timeline plot of login node job activity over time."""
    
    # Load data
    data = load_job_data(json_file_path)
    
    if not data:
        return False
    
    if 'error' in data.get('job_runs', {}):
        print(f"Error in data: {data['job_runs']['error']}")
        return False
    
    jobs = data['job_runs']['jobs']
    
    if not jobs:
        print("No job data found")
        return False
    
    # Count all jobs in the data (no time filtering - JSON is already 48hr window)
    jobs_in_window = sum(len(job_data['runs_detail']) for job_data in jobs.values())
    
    # Prepare metadata
    metadata = data.get('metadata', {})
    summary = data['job_runs'].get('summary', {})
    metadata['total_unique_scripts'] = summary.get('total_unique_scripts', len(jobs))
    
    # Generate HTML
    html_content = generate_plotly_html(jobs, metadata, jobs_in_window)
    
    # Write to file
    with open(output_file_path, 'w') as f:
        f.write(html_content)
    
    print(f"Generated {output_file_path} with {len(jobs)} login node scripts")
    print(f"Data from: {metadata.get('generated_time', 'Unknown')}")
    print(f"Jobs in time window: {jobs_in_window}")
    print(f"Total runtime tracked: {summary.get('total_duration_seconds', 0):.0f} seconds ({summary.get('total_duration_seconds', 0)/3600:.1f} hours)")
    
    return True

def main():
    """Main function."""
    # Default paths - can be overridden with command line args
    json_file = sys.argv[1] if len(sys.argv) > 1 else 'dashboard_login_jobs.json'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'login_jobs_timeline.html'
    
    success = generate_timeline_plot(json_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
