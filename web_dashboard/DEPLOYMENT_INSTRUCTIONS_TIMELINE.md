# EarthCast HPC Cluster Usage Timeline Integration

## Architecture Overview

The cluster usage monitoring is split into two components:

1. **HPC Cluster (erthch)**: Data collection only
   - Runs `myusage` command hourly via cron
   - Generates `dashboard_cluster_usage.json` with job data  
   - Pushes JSON to web server via SCP

2. **Web Server (rcity2.cottay.net)**: Visualization generation
   - Receives JSON file from HPC cluster
   - Generates interactive timeline HTML on-demand
   - Serves static HTML files to users

## What Changed: Scatter Plot → Timeline

**Before**: Scatter plot with dots sized by core usage
**After**: Timeline with horizontal bars showing job duration

### Key Improvements:
- **Job Duration Focus**: Shows when jobs actually ran (start to end time)
- **Core-Based Sorting**: Jobs sorted by core count (highest at top)
- **Better Readability**: Horizontal grid lines separate job rows
- **Same Production Quality**: Maintains all existing functionality

## Files to Deploy

### Web Server Files (deploy to rcity2.cottay.net:/srv/www/earthcast/)

1. **web_server_timeline_plot.py** - Python script to generate timeline from JSON
2. **web_server_generate_timeline.sh** - Shell script wrapper for timeline generation

### Current HPC Cluster Setup (no changes needed)

- `dashboard_cluster_usage.py` - Collects data from myusage command (unchanged)
- `update_cluster_usage_cron.sh` - Cron script (unchanged)
- Cron job: `0 * * * * /e/08/erthch01/monitoring/web_dashboard/update_cluster_usage_cron.sh`

## Deployment Steps

### 1. Deploy to Web Server

```bash
# Copy new timeline files to web server
scp web_server_timeline_plot.py will@rcity2.cottay.net:/srv/www/earthcast/
scp web_server_generate_timeline.sh will@rcity2.cottay.net:/srv/www/earthcast/

# On web server, make executable
ssh will@rcity2.cottay.net "chmod +x /srv/www/earthcast/web_server_generate_timeline.sh"
```

### 2. Update Cron Job on Web Server

Replace the existing scatter plot cron job with timeline generation:

```bash
# On web server (rcity2.cottay.net)
crontab -e

# Replace this line:
# 5 * * * * /srv/www/earthcast/web_server_generate_plot.sh >/dev/null 2>&1

# With this line:
5 * * * * /srv/www/earthcast/web_server_generate_timeline.sh >/dev/null 2>&1
```

### 3. Generate Initial Timeline

```bash
# On web server, run manually first time
cd /srv/www/earthcast
./web_server_generate_timeline.sh
```

### 4. Web Access

The timeline will be available at:
- **http://rcity2.cottay.net/earthcast/cluster_usage_timeline.html**

## Features

- **36-hour time window** (excludes last 4 hours to avoid incomplete jobs)
- **Job grouping** (metgrid_real_wrf.PBS.date.hour → metgrid_real_wrf.PBS.00Z/12Z)
- **Interactive tooltips** with job details (same as scatter plot)
- **Core-based sorting** (highest core jobs at top for priority visibility)
- **Duration visualization** (horizontal bars show actual job runtime)
- **Grid lines** (light horizontal lines separate job rows)
- **No dependencies** on HPC cluster plotly installation

## Monitoring

- JSON file updated hourly by HPC cluster (unchanged)
- Web server script checks JSON file age (warns if >2 hours old)
- Generated HTML file size ~227KB (similar to scatter plot)
- Cron logs on HPC cluster show data collection status (unchanged)

## Migration Notes

### Data Compatibility
- ✅ **Same JSON format**: Uses existing `dashboard_cluster_usage.json`
- ✅ **Same data source**: No changes to HPC cluster data collection
- ✅ **Same time window**: 36-hour window excluding last 4 hours

### File Changes
- `cluster_usage_scatter.html` → `cluster_usage_timeline.html`
- `web_server_scatter_plot.py` → `web_server_timeline_plot.py`
- `web_server_generate_plot.sh` → `web_server_generate_timeline.sh`

### Rollback Plan
If needed, you can easily rollback by:
1. Reverting the cron job to use `web_server_generate_plot.sh`
2. The old scatter plot files remain unchanged

## Benefits of Timeline vs Scatter Plot

1. **Duration Visibility**: See exactly how long jobs ran
2. **Resource Priority**: High-core jobs prominently displayed at top
3. **Timeline Context**: Better understanding of job scheduling patterns
4. **Visual Clarity**: Horizontal bars easier to read than varying dot sizes
5. **Grid Structure**: Clean separation between different job types
