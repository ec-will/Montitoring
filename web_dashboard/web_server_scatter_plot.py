#!/usr/bin/env python3
"""
Web Server Scatter Plot Generator for EarthCast HPC Cluster Usage
Reads dashboard_cluster_usage.json and generates cluster_usage_scatter.html
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
    """Generate the HTML with embedded Plotly scatter plot."""
    
    # More vibrant color palette
    job_colors = {}
    colors = ['#FF1744', '#00BCD4', '#4CAF50', '#FF9800', '#9C27B0',
              '#FF5722', '#E91E63', '#607D8B', '#FFC107', '#00E676',
              '#3F51B5', '#FF6F00', '#00C853', '#D500F9', '#FF3D00']
    color_idx = 0
    
    # Set time window: 40 hours ago to 4 hours ago (36 hours total)
    end_time = datetime.now() - timedelta(hours=4)
    start_time = end_time - timedelta(hours=36)
    
    # Sort jobs by normalized name for consistent ordering
    sorted_jobs = sorted(grouped_jobs.keys())
    
    # Prepare plot data
    plot_data = []
    
    for job_idx, normalized_name in enumerate(sorted_jobs):
        job_group = grouped_jobs[normalized_name]
        
        # Get color for this job type (based on prefix)
        job_type = normalized_name.split('_')[0] if '_' in normalized_name else normalized_name[:10]
        if job_type not in job_colors:
            job_colors[job_type] = colors[color_idx % len(colors)]
            color_idx += 1
        
        color = job_colors[job_type]
        
        # Collect points for this job group
        points = []
        
        for run in job_group['runs_detail']:
            if not run.get('end'):
                continue
                
            try:
                # Parse end time
                end_time_str = run['end']
                if 'T' in end_time_str:
                    run_end_time = datetime.strptime(end_time_str.replace('T', ' ').replace('Z', ''), '%Y-%m-%d %H:%M:%S')
                else:
                    run_end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
                
                # Only include jobs within our time window
                if start_time <= run_end_time <= end_time:
                    # Size based on core hours (min 8, max 35)
                    size = max(8, min(35, run['core_hours'] * 2 + 8))
                    
                    points.append({
                        'x': run_end_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'y': job_idx,
                        'size': size,
                        'hover': f"Job: {normalized_name}<br>End Time: {end_time_str}<br>Core Hours: {run['core_hours']}<br>Cores: {run['cores']}<br>Cluster: {run['cluster']}"
                    })
                    
            except (ValueError, TypeError):
                continue
        
        if points:
            plot_data.append({
                'name': normalized_name,
                'color': color,
                'points': points
            })
    
    # Generate job labels for y-axis
    job_labels = [job.replace('.csh', '').replace('run_', '') for job in sorted_jobs]
    
    # Create HTML with embedded Plotly
    html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>EarthCast HPC Cluster Usage Timeline</title>
    <script src="https://cdn.plot.ly/plotly-2.25.2.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .info {{ margin-bottom: 20px; padding: 15px; background-color: #ffffff; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        #plotDiv {{ background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>EarthCast HPC Cluster Usage Timeline</h1>
    <div class="info">
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Data Source:</strong> {data_metadata.get('data_source', 'Unknown')}</p>
        <p><strong>Data Generated:</strong> {data_metadata.get('generated_time', 'Unknown')}</p>
        <p><strong>Time Window:</strong> Last 36 hours (excluding most recent 4 hours)</p>
        <p><strong>Total Job Groups:</strong> {len(grouped_jobs)} (grouped from {data_metadata.get('total_original_jobs', 'unknown')} individual job names)</p>
        <p><strong>Jobs in Window:</strong> {jobs_in_window} job runs displayed</p>
        <p><strong>Note:</strong> Dot size represents core hours used by each job run. Jobs with date.hour patterns are grouped by hour (00Z/12Z).</p>
    </div>
    <div id="plotDiv"></div>

    <script>
        var traces = [];
        var plotData = {json.dumps(plot_data)};
        var jobLabels = {json.dumps(job_labels)};
        
        plotData.forEach(function(jobGroup) {{
            if (jobGroup.points.length > 0) {{
                var trace = {{
                    x: jobGroup.points.map(p => p.x),
                    y: jobGroup.points.map(p => p.y),
                    mode: 'markers',
                    name: jobGroup.name,
                    showlegend: false,
                    marker: {{
                        size: jobGroup.points.map(p => p.size),
                        color: jobGroup.color,
                        opacity: 0.9,
                        line: {{
                            width: 1,
                            color: 'white'
                        }}
                    }},
                    text: jobGroup.points.map(p => p.hover),
                    hovertemplate: '%{{text}}<extra></extra>'
                }};
                traces.push(trace);
            }}
        }});

        var layout = {{
            title: {{
                text: 'Cluster Job Usage Timeline (36-hour window)',
                x: 0.5,
                xanchor: 'center'
            }},
            xaxis: {{
                title: 'Job End Time',
                gridcolor: '#333333',
                gridwidth: 1,
                showgrid: true,
                zeroline: false,
                linecolor: '#333333',
                linewidth: 2
            }},
            yaxis: {{
                title: 'Jobs',
                tickmode: 'array',
                tickvals: Array.from({{length: jobLabels.length}}, (_, i) => i),
                ticktext: jobLabels,
                tickfont: {{size: 10}},
                showgrid: false,
                zeroline: false,
                linecolor: '#333333',
                linewidth: 2
            }},
            hovermode: 'closest',
            height: Math.max(600, jobLabels.length * 25 + 200),
            width: 1400,
            margin: {{l: 250, r: 50, t: 80, b: 80}},
            plot_bgcolor: '#f0f8ff',
            paper_bgcolor: 'white'
        }};

        Plotly.newPlot('plotDiv', traces, layout, {{responsive: true}});
    </script>
</body>
</html>'''
    
    return html_content

def generate_scatter_plot(json_file_path, output_file_path):
    """Generate interactive scatter plot of job usage over time."""
    
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
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'cluster_usage_scatter.html'
    
    success = generate_scatter_plot(json_file, output_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
