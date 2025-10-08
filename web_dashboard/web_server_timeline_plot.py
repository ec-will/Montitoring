#!/usr/bin/env python3
"""
Web Server Timeline Plot Generator for EarthCast HPC Cluster Usage
Reads dashboard_cluster_usage.json and generates cluster_usage_timeline.html
Should be run on the web server after receiving updated JSON data.
"""

import json
import sys
import os
from datetime import datetime, timedelta
import re

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

def normalize_job_name(job_name):
    """Normalize job names to group similar jobs together."""
    # Handle metgrid_real_wrf.PBS.date.hour pattern - group by hour only
    metgrid_match = re.match(r'metgrid_real_wrf\.PBS\.\d{8}(\d{2})\.csh', job_name)
    if metgrid_match:
        hour = metgrid_match.group(1)
        return f'metgrid_real_wrf.PBS.{hour}Z.csh'
    
    # Return original name for other jobs
    return job_name

def generate_plotly_html(grouped_jobs, data_metadata, jobs_in_window):
    """Generate the HTML with embedded Plotly timeline visualization."""
    
    # Same vibrant color palette as production
    job_colors = {}
    colors = ['#FF1744', '#00BCD4', '#4CAF50', '#FF9800', '#9C27B0',
              '#FF5722', '#E91E63', '#607D8B', '#FFC107', '#00E676',
              '#3F51B5', '#FF6F00', '#00C853', '#D500F9', '#FF3D00']
    color_idx = 0
    
    # Set time window: 40 hours ago to 4 hours ago (36 hours total)
    end_time = datetime.now() - timedelta(hours=4)
    start_time = end_time - timedelta(hours=36)
    
    # Calculate average cores for each job group for sorting
    job_core_stats = {}
    for normalized_name, job_group in grouped_jobs.items():
        total_cores = 0
        count = 0
        for run in job_group['runs_detail']:
            if run.get('cores'):
                total_cores += run['cores']
                count += 1
        avg_cores = total_cores / count if count > 0 else 0
        job_core_stats[normalized_name] = avg_cores
    
    # Sort jobs by average core count (descending - highest core jobs at top)
    sorted_jobs = sorted(grouped_jobs.keys(), key=lambda x: job_core_stats.get(x, 0), reverse=True)
    
    # Prepare plot data
    plot_data = []
    num_jobs = len(sorted_jobs)
    
    for job_idx, normalized_name in enumerate(sorted_jobs):
        job_group = grouped_jobs[normalized_name]
        
        # Get color for this job type (based on prefix)
        job_type = normalized_name.split('_')[0] if '_' in normalized_name else normalized_name[:10]
        if job_type not in job_colors:
            job_colors[job_type] = colors[color_idx % len(colors)]
            color_idx += 1
        
        color = job_colors[job_type]
        
        # Collect bars for this job group
        bars = []
        
        for run in job_group['runs_detail']:
            if not run.get('end') or not run.get('start'):
                continue
                
            try:
                # Parse start and end times
                end_time_str = run['end']
                start_time_str = run['start']
                
                if 'T' in end_time_str:
                    run_end_time = datetime.strptime(end_time_str.replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                    run_start_time = datetime.strptime(start_time_str.replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    run_end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
                    run_start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                
                # Only include jobs within our time window
                if start_time <= run_end_time <= end_time:
                    duration_hours = (run_end_time - run_start_time).total_seconds() / 3600
                    
                    # Reverse Y position so highest cores appear at top
                    y_pos = num_jobs - 1 - job_idx
                    
                    bars.append({
                        'start': run_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'end': run_end_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'y': y_pos,
                        'cores': run.get('cores', 0),
                        'hover': f"Job: {normalized_name}<br>Start: {start_time_str}<br>End: {end_time_str}<br>Duration: {duration_hours:.2f} hours<br>Core Hours: {run['core_hours']}<br>Cores: {run['cores']}<br>Cluster: {run['cluster']}"
                    })
                    
            except (ValueError, TypeError):
                continue
        
        if bars:
            plot_data.append({
                'name': normalized_name,
                'color': color,
                'bars': bars,
                'avg_cores': job_core_stats.get(normalized_name, 0)
            })
    
    # Generate job labels for y-axis with core info - reverse order to match Y positions
    job_labels = []
    for job in reversed(sorted_jobs):  # Reverse to match the reversed Y positions
        label = job.replace('.csh', '').replace('run_', '')
        avg_cores = job_core_stats.get(job, 0)
        if avg_cores > 0:
            label += f' ({avg_cores:.0f} cores)'
        job_labels.append(label)
    
    # Create HTML with embedded Plotly
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>EarthCast HPC Cluster Usage Timeline</title>
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
                text: 'Cluster Job Usage Timeline (36-hour window)',
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
                title: 'Jobs (sorted by cores descending)',
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
    """Generate interactive timeline plot of job usage over time."""
    
    # Load data
    data = load_job_data(json_file_path)
    
    if not data:
        return False
    
    if 'error' in data.get('job_usage', {}):
        print(f"Error in data: {data['job_usage']['error']}")
        return False
    
    jobs = data['job_usage']['jobs']
    
    if not jobs:
        print("No job data found")
        return False
    
    # Group jobs by normalized names
    grouped_jobs = {}
    for job_name, job_data in jobs.items():
        normalized_name = normalize_job_name(job_name)
        if normalized_name not in grouped_jobs:
            grouped_jobs[normalized_name] = {
                'runs_detail': [],
                'original_names': []
            }
        grouped_jobs[normalized_name]['runs_detail'].extend(job_data['runs_detail'])
        grouped_jobs[normalized_name]['original_names'].append(job_name)
    
    # Count jobs in time window
    end_time = datetime.now() - timedelta(hours=4)
    start_time = end_time - timedelta(hours=36)
    
    jobs_in_window = sum(1 for job_group in grouped_jobs.values() 
                        for run in job_group['runs_detail'] 
                        if run.get('end') and start_time <= datetime.strptime(run['end'].replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S') <= end_time)
    
    # Prepare metadata
    metadata = data.get('metadata', {})
    metadata['total_original_jobs'] = len(jobs)
    
    # Generate HTML
    html_content = generate_plotly_html(grouped_jobs, metadata, jobs_in_window)
    
    # Write to file
    with open(output_file_path, 'w') as f:
        f.write(html_content)
    
    print(f"Generated {output_file_path} with {len(grouped_jobs)} job groups (from {len(jobs)} individual jobs)")
    print(f"Data from: {metadata.get('generated_time', 'Unknown')}")
    print(f"Jobs in time window: {jobs_in_window}")
    
    # Show grouping info
    metgrid_groups = {k: v for k, v in grouped_jobs.items() if 'metgrid_real_wrf' in k}
    if metgrid_groups:
        print("Metgrid job grouping:")
        for group_name, group_data in metgrid_groups.items():
            original_names = group_data['original_names']
            print(f"  {group_name} <- {', '.join(original_names)}")
    
    return True

def main():
    """Main function."""
    # Default paths - can be overridden with command line args
    json_file = sys.argv[1] if len(sys.argv) > 1 else 'dashboard_cluster_usage.json'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'cluster_usage_timeline.html'
    
    success = generate_timeline_plot(json_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
