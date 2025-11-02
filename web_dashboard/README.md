# EarthCast HPC Dashboard

A real-time web dashboard for monitoring HPC cluster workflows, PBS jobs, and system metrics.

## Features

- **Real-time Monitoring**: Updates every 5 minutes via automated cron job
- **Workflow Status**: Live status of weather modeling workflows with expandable logs
- **PBS Job Details**: Active job monitoring with detailed `mqstat -f` information
- **Node Utilization**: Color-coded compute node status with utilization percentages
- **System Metrics**: Disk, memory, load average, and log activity monitoring
- **Responsive Design**: Mobile-friendly interface with professional styling
- **EarthCast Branding**: Company logo and consistent visual design

## Architecture

### Data Collection (`update_dashboard.py`)
- Queries PBS/Torque for active jobs
- Monitors workflow status via existing scripts
- Collects system metrics (disk, memory, uptime)
- Executes `ectnodes` for compute node utilization
- Generates JSON data file for web consumption

### Web Interface (`index.html`)
- Modern HTML5/CSS3/JavaScript dashboard
- Two-column layout for optimal information density
- Interactive elements (expandable logs/job details)
- Color-coded status indicators and utilization metrics
- Automatic refresh and error handling

### Deployment (`update_dashboard_cron.sh`)
- Automated data generation and deployment
- Robust error handling and logging
- File transfer to nginx web server
- Lock file management to prevent overlapping runs

## Installation

1. **Set up file structure**:
   ```bash
   /e/08/erthch01/monitoring/web_dashboard/
   ├── index.html                    # Web dashboard
   ├── update_dashboard.py           # Data generator
   ├── update_dashboard_cron.sh      # Deployment script
   ├── earthcast-logo.png           # Logo asset
   └── dashboard_data.json          # Generated data (ignored by git)
   ```

2. **Configure cron job** (runs every 5 minutes):
   ```bash
   */5 * * * * /e/08/erthch01/monitoring/web_dashboard/update_dashboard_cron.sh
   ```

3. **Web server deployment**:
   - Files deployed to: `rcity2.cottay.net:/srv/www/earthcast/`
   - Served via nginx with appropriate security headers

## Dependencies

- **Python 3**: Data processing and JSON generation
- **PBS/Torque**: `qstat`, `mqstat` commands
- **System tools**: `df`, `free`, `uptime`, `find`
- **Custom tools**: `ectnodes` for node status
- **Web server**: nginx for serving static files

## Data Sources

- **Workflows**: Direct log file reading from `/e/08/erthch01/logs/wrf/` with Python analysis
- **PBS Jobs**: Direct `qstat -f` and `mqstat -f` parsing
- **Node Status**: Custom `ectnodes` command
- **System Metrics**: Standard Linux utilities
- **Log Files**: Direct file reading in `/e/08/erthch01/logs/`

## Security

- Read-only data collection from HPC systems
- Static file serving with no server-side execution
- Proper error handling to prevent information disclosure
- Regular log rotation and cleanup

## Monitoring

- Logs: `/e/08/erthch01/logs/dashboard/update_dashboard.log`
- Lock files: `/tmp/dashboard_update.lock`
- Update frequency: Every 5 minutes
- Data retention: Last 100 log entries

## Version History

- **v1.0** (2025-10-05): Initial release with full HPC monitoring features

## Maintenance

- **Log monitoring**: Check `/e/08/erthch01/logs/dashboard/` for errors
- **Cron status**: Verify 5-minute update schedule
- **Web access**: Monitor nginx logs for access patterns
- **Data validation**: JSON structure should remain consistent

---

*EarthCast HPC Dashboard - Real-time cluster monitoring and visualization*
# Last updated: Tue Oct 14 16:27:12 EDT 2025
