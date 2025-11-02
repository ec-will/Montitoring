# EarthCast HPC Cluster Usage Scatter Plot Integration

## Architecture Overview

The cluster usage monitoring is split into two components:

1. **HPC Cluster (erthch)**: Data collection only
   - Runs `myusage` command hourly via cron
   - Generates `dashboard_cluster_usage.json` with job data  
   - Pushes JSON to web server via SCP

2. **Web Server (rcity2.cottay.net)**: Visualization generation
   - Receives JSON file from HPC cluster
   - Generates interactive scatter plot HTML on-demand
   - Serves static HTML files to users

## Files to Deploy

### Web Server Files (deploy to rcity2.cottay.net:/srv/www/earthcast/)

1. **web_server_scatter_plot.py** - Python script to generate scatter plot from JSON
2. **web_server_generate_plot.sh** - Shell script wrapper for plot generation

### Current HPC Cluster Setup (already configured)

- `dashboard_cluster_usage.py` - Collects data from myusage command
- `update_cluster_usage_cron.sh` - Cron script (fixed PATH/PERL5LIB issues)
- Cron job: `0 * * * * /e/08/erthch01/monitoring/web_dashboard/update_cluster_usage_cron.sh`

## Deployment Steps

### 1. Deploy to Web Server

```bash
# Copy files to web server
scp web_server_scatter_plot.py will@rcity2.cottay.net:/srv/www/earthcast/
scp web_server_generate_plot.sh will@rcity2.cottay.net:/srv/www/earthcast/

# On web server, make executable
ssh will@rcity2.cottay.net "chmod +x /srv/www/earthcast/web_server_generate_plot.sh"
```

### 2. Set Up Web Server Plot Generation

Option A: **Manual generation** (run when needed)
```bash
# On web server
cd /srv/www/earthcast
./web_server_generate_plot.sh
```

Option B: **Automatic generation** (recommended)
```bash
# On web server, add to crontab to run a few minutes after JSON arrives
# Since HPC pushes at :00, generate plot at :05
crontab -e
# Add: 5 * * * * /srv/www/earthcast/web_server_generate_plot.sh >/dev/null 2>&1
```

### 3. Web Access

The scatter plot will be available at:
- http://rcity2.cottay.net/earthcast/cluster_usage_scatter.html

## Features

- **36-hour time window** (excludes last 4 hours to avoid incomplete jobs)
- **Job grouping** (metgrid_real_wrf.PBS.date.hour → metgrid_real_wrf.PBS.00Z/12Z)
- **Interactive tooltips** with job details
- **Responsive sizing** based on core hours used
- **Pale blue background** with vibrant colored dots
- **No dependencies** on HPC cluster plotly installation

## Monitoring

- JSON file updated hourly by HPC cluster
- Web server script checks JSON file age (warns if >2 hours old)
- Generated HTML file size indicates successful generation (~200KB with data)
- Cron logs on HPC cluster show data collection status

## Benefits of This Architecture

1. **Separation of concerns**: Data collection vs visualization
2. **Reduced HPC dependencies**: No need for plotly on compute cluster  
3. **Web server optimization**: Plot generation uses web server resources
4. **Scalability**: Can add more visualizations without affecting HPC cluster
5. **Reliability**: If plot generation fails, data collection continues
