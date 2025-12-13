# Timeline Deployment - Updated Architecture

## Overview

Both cluster and login node timelines now use the same deployment approach:
1. **HPC generates HTML** from JSON locally
2. **HPC pushes ready-to-display HTML** to web servers
3. **Web servers simply serve static HTML** (no Python, no cron needed on web server)

## What Changed

### Cluster Usage Timeline
**Before:** HPC pushes JSON → Web server cron watches JSON → Web server generates HTML  
**After:** HPC generates HTML → HPC pushes HTML → Web server serves HTML

**Modified file:** `update_cluster_usage_cron.sh`
- Now calls `web_server_timeline_plot.py` to generate HTML on HPC
- Pushes `cluster_usage_timeline.html` instead of just JSON
- Still runs hourly via cron: `0 * * * *`

### Login Jobs Timeline
**New deployment:** `deploy_login_timeline.sh`
- Generates HTML from `dashboard_login_jobs.json`
- Pushes `login_jobs_timeline.html` to web servers
- Recommended cron: `*/5 * * * *` (every 5 minutes) or `*/10 * * * *` (every 10 minutes)

## Deployment Steps

### 1. Update Cluster Timeline (jeffsc8)

```bash
cd /e/08/erthch01/monitoring/web_dashboard

# Copy updated deployment script
scp update_cluster_usage_cron.sh jeffsc8:/e/08/erthch01/monitoring/web_dashboard/

# Test it manually first
ssh jeffsc8
cd /e/08/erthch01/monitoring/web_dashboard
./update_cluster_usage_cron.sh

# Check logs
tail -20 /e/08/erthch01/logs/dashboard/update_cluster_usage.log

# Verify HTML was generated and pushed
ls -lh cluster_usage_timeline.html
ssh rcity2.cottay.net "ls -lh /srv/www/earthcast/cluster_usage_timeline.html"
```

### 2. Deploy Login Timeline (jeffsc8)

```bash
cd /e/08/erthch01/monitoring/web_dashboard

# Copy files to HPC
scp web_server_login_timeline_plot.py jeffsc8:/e/08/erthch01/monitoring/web_dashboard/
scp deploy_login_timeline.sh jeffsc8:/e/08/erthch01/monitoring/web_dashboard/

# Make executable and test
ssh jeffsc8
cd /e/08/erthch01/monitoring/web_dashboard
chmod +x deploy_login_timeline.sh
./deploy_login_timeline.sh

# Check logs
tail -20 /e/08/erthch01/logs/dashboard/deploy_login_timeline.log

# Add to crontab (every 10 minutes)
crontab -e
# Add this line:
*/10 * * * * /e/08/erthch01/monitoring/web_dashboard/deploy_login_timeline.sh
```

### 3. Remove Web Server Cron Jobs (if any exist)

Since HTML is now generated on HPC, remove any timeline-related cron jobs from web servers:

```bash
# On rcity2.cottay.net
ssh rcity2.cottay.net
crontab -l | grep -i timeline  # Check for timeline-related jobs
# If any exist, remove them via crontab -e

# On ect-hpc.wx-farms.com (if applicable)
ssh ect-hpc.wx-farms.com
crontab -l | grep -i timeline
```

## File Locations

### HPC (jeffsc8:/e/08/erthch01/monitoring/web_dashboard/)
- `dashboard_cluster_usage.py` - Collects cluster job data (unchanged)
- `update_cluster_usage_cron.sh` - **Modified** - Now generates HTML and pushes it
- `web_server_timeline_plot.py` - Generates cluster timeline HTML
- `dashboard_login_jobs.py` - Collects login job data (continuously running)
- `web_server_login_timeline_plot.py` - **New** - Generates login timeline HTML
- `deploy_login_timeline.sh` - **New** - Deployment script for login timeline
- `dashboard_login_jobs.json` - Login jobs data (updated by tracker)
- `cluster_usage_timeline.html` - Generated HTML (pushed to web)
- `login_jobs_timeline.html` - Generated HTML (pushed to web)

### Web Servers (rcity2.cottay.net, ect-hpc.wx-farms.com:/srv/www/earthcast/)
- `cluster_usage_timeline.html` - Ready-to-display cluster timeline
- `login_jobs_timeline.html` - Ready-to-display login timeline
- `index.html` - Main dashboard (embeds both timelines)

## Cron Schedule

### HPC (jeffsc8)
```
# Login node job tracker (continuous monitoring)
@reboot /e/08/erthch01/monitoring/web_dashboard/start_login_tracker.sh
*/10 * * * * /e/08/erthch01/monitoring/web_dashboard/start_login_tracker.sh

# Cluster usage data collection and HTML deployment (hourly)
0 * * * * /e/08/erthch01/monitoring/web_dashboard/update_cluster_usage_cron.sh

# Login timeline HTML deployment (every 10 minutes)
*/10 * * * * /e/08/erthch01/monitoring/web_dashboard/deploy_login_timeline.sh
```

### Web Servers
**No cron jobs needed** - just serve static HTML files

## Benefits of New Approach

1. **Simpler architecture** - Web server just serves files
2. **Fewer moving parts** - No Python needed on web server
3. **No cron synchronization** - Don't need to watch for file changes
4. **Consistent approach** - Both timelines deployed the same way
5. **Better error handling** - Generation errors logged on HPC where data lives
6. **Easier debugging** - All processing happens in one place

## Integration with index.html

Both timelines are embedded as iframes in `index.html`:

```html
<!-- Cluster Usage Timeline -->
<iframe src="cluster_usage_timeline.html" width="100%" height="800px" frameborder="0"></iframe>

<!-- Login Jobs Timeline -->
<iframe src="login_jobs_timeline.html" width="100%" height="800px" frameborder="0"></iframe>
```

Both HTML files have minimal styling since they inherit from index.html.

## Logs

### Cluster Timeline
- **Location:** `/e/08/erthch01/logs/dashboard/update_cluster_usage.log`
- **Check with:** `tail -50 /e/08/erthch01/logs/dashboard/update_cluster_usage.log`

### Login Timeline
- **Location:** `/e/08/erthch01/logs/dashboard/deploy_login_timeline.log`
- **Check with:** `tail -50 /e/08/erthch01/logs/dashboard/deploy_login_timeline.log`

## Verification

After deployment, verify both timelines are accessible:
- Cluster: http://rcity2.cottay.net/earthcast/cluster_usage_timeline.html
- Login: http://rcity2.cottay.net/earthcast/login_jobs_timeline.html
- Dashboard: http://rcity2.cottay.net/earthcast/index.html
