# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Overview

This is the EarthCast HPC Monitoring Dashboard repository, which provides comprehensive monitoring for weather forecasting operations. It consists of two main components:

1. **Terminal Dashboard**: Real-time command-line monitoring of HPC workflows and PBS jobs
2. **Web Dashboard**: Browser-based dashboard with automated updates and detailed visualizations

## Essential Commands

### Dashboard Operations
```bash
# Load dashboard aliases (required for commands below)
source $HOME/monitoring/aliases.sh

# Show current system status
dashboard

# Auto-refresh monitoring (30-second intervals)
monitor

# Alternative status command
hpc-status
```

### Log Analysis Commands
```bash
# Check recent workflow logs
check-wrf      # Global WRF logs
check-mrms     # MRMS radar logs
check-hiresw   # HiResW model logs
check-drone    # Drone weather logs

# System status
pbs-status     # PBS job queue
disk-status    # Disk usage
log-activity   # Recent log file count
```

### Web Dashboard Management
```bash
# Generate/update web dashboard data (manual)
cd web_dashboard && python3 update_dashboard.py

# Deploy to web server (manual)
cd web_dashboard && ./update_dashboard_cron.sh

# Generate cluster usage scatter plot (manual)
cd web_dashboard && python3 dashboard_cluster_usage.py

# View web dashboard logs
tail -f /e/08/erthch01/logs/dashboard/update_dashboard.log
```

## Architecture Overview

### Terminal Dashboard (`scripts/dashboard_v18.sh`)
- **Intelligent Status Detection**: Analyzes log contents to differentiate between failures, waiting states, and successes
- **WRF File Counting**: Validates workflow completion by counting wrfout files (Global WRF ~37 files, AccuWeather regions ~33 files)
- **Real-time PBS Integration**: Shows active jobs with resource usage and full script names
- **Smart Scheduling**: Displays next expected run times based on workflow schedules

### Web Dashboard Architecture
- **Data Collection** (`update_dashboard.py`): Python script that directly reads logs, queries PBS/Torque, and collects system metrics
- **Web Interface** (`index.html`): Modern HTML5/CSS3/JavaScript dashboard with interactive elements
- **Automated Deployment** (`update_dashboard_cron.sh`): Cron-based script that generates data and deploys to web server every 5 minutes
- **Cluster Usage Monitoring** (`dashboard_cluster_usage.py`): Hourly job usage tracking with scatter plot visualization

### Key Data Sources
- **Workflows**: Direct log file reading from `/e/08/erthch01/logs/wrf/` with status analysis
- **PBS Jobs**: Direct `qstat -f` and `mqstat -f` parsing for detailed job information
- **Node Status**: Custom `ectnodes` command for compute node utilization
- **System Metrics**: Standard Linux utilities (`df`, `free`, `uptime`, `find`)
- **Log Analysis**: Python-based intelligent status parsing for WRF workflows
- **Job Usage**: Historical job data via `myusage` command for cluster utilization analysis

## Workflow Monitoring Logic

### Status Detection Strategy
The dashboard uses sophisticated log analysis to determine workflow states:

1. **Failure Detection**: Looks for `killed`, `abort`, `fatal`, `exception` in recent log entries
2. **External Data Waiting**: Distinguishes between local processing delays and upstream data availability issues (GFS, NOAA delays)
3. **Running State**: Detects active processing through recent timestamps and PBS activity indicators
4. **Success Validation**: Combines exit status with output file counting for accurate completion detection

### WRF Output Validation
Critical for detecting incomplete runs even when exit status appears successful:
- **Global WRF**: ~37 wrfout files expected for 36-hour runs
- **AccuWeather Asia**: ~33 files for regional runs  
- **AccuWeather Europe**: ~33 files for regional runs

Low file counts indicate premature termination requiring investigation.

### Workflow Schedules
- **Global WRF**: 03:25 and 15:25 UTC (00Z and 12Z cycles)
- **AccuWeather Asia/Europe**: 04:29, 10:29, 16:29, 22:29 UTC (6-hourly)
- **HiResW**: 04:38 and 16:38 UTC (00Z and 12Z cycles)
- **MRMS**: Every 5 minutes (real-time radar data)
- **Drone Weather**: Hourly at XX:10

## Development Workflows

### Testing Changes
```bash
# Test terminal dashboard locally
./scripts/dashboard_v18.sh

# Test web dashboard data collection
cd web_dashboard && python3 update_dashboard.py

# Validate generated JSON structure
cd web_dashboard && python3 -m json.tool dashboard_data.json
```

### Development Guidelines

### Working with Log Analysis
When modifying log analysis functions (`analyze_log_status`, `analyze_log_status_detailed`):
- Preserve the hierarchy: failures → external waiting → running → success
- External data delays should be treated as legitimate waiting states, not failures
- File age thresholds are workflow-specific and tuned for operational patterns

### Adding New Workflows
1. Add log analysis patterns in `analyze_log_status()` in `update_dashboard.py`
2. Define expected schedules in `get_dynamic_next_run()`
3. If WRF-based, add output file counting logic in `get_workflows()`
4. Update workflow list in `get_workflows()` function
5. Test with `python3 update_dashboard.py` before deploying

### Web Dashboard Development
- JSON data structure is generated by `update_dashboard.py` in the web_dashboard directory
- Web interface expects specific JSON schema - maintain compatibility when modifying data collection  
- Cron deployment runs every 5 minutes - test changes thoroughly before deploying
- Test locally with `python3 update_dashboard.py` before deploying to web server
- Cluster usage data is collected hourly and deployed separately from main dashboard

### PBS Integration
The system parses both `qstat -f` and `mqstat -f` output:
- `qstat -f`: Standard job listing with resources and state
- `mqstat -f`: Detailed Moab scheduler information for job details display
- Resource parsing handles `nodes:ppn` format for accurate core counting

## File Structure Context

```
monitoring/
├── scripts/                    # Dashboard implementations
│   ├── dashboard_v18.sh       # Current terminal dashboard (main)
│   └── dashboard_v[1-17].sh   # Historical versions (legacy)
├── web_dashboard/             # Web dashboard components
│   ├── index.html            # Browser interface
│   ├── update_dashboard.py   # Data collection script
│   ├── update_dashboard_cron.sh # Deployment automation
│   ├── dashboard_cluster_usage.py # Cluster usage data collection
│   ├── update_cluster_usage_cron.sh # Hourly usage update
│   ├── web_server_scatter_plot.py # Cluster usage visualization
│   ├── web_server_generate_plot.sh # Plot generation wrapper
│   ├── DEPLOYMENT_INSTRUCTIONS.md # Web server deployment guide
│   └── dashboard_data.json   # Generated data (ignored by git)
├── aliases.sh                # Command aliases and PATH setup
└── README.md                 # User documentation
```

## Troubleshooting

### Dashboard Not Updating
1. Check cron job: `*/5 * * * * /e/08/erthch01/monitoring/web_dashboard/update_dashboard_cron.sh`
2. Verify lock file not stuck: `ls -la /tmp/dashboard_update.lock`
3. Check logs: `tail -50 /e/08/erthch01/logs/dashboard/update_dashboard.log`

### PBS Commands Failing
- Ensure PATH includes Torque tools: `export PATH="/usr/local/torque-4.2.8/bin:$PATH"`
- Test basic commands: `qstat -u erthch01`, `mqstat -f <job_id>`

### Log Analysis Issues
- Log paths are hardcoded to `/e/08/erthch01/logs/` and `$HOME/logs/`
- Workflow-specific log filename patterns are defined in the scripts
- Use `find /e/08/erthch01/logs -name "*pattern*" -mtime -1` to locate recent logs

## System Dependencies

### Required Commands
- **PBS/Torque**: `qstat`, `mqstat` 
- **Python 3**: For web dashboard data processing
- **System Tools**: `df`, `free`, `uptime`, `find`, `tail`, `stat`
- **Custom Tools**: `ectnodes` (compute node status)
- **Network Tools**: `scp` (for web deployment)

### Environment Requirements
- Home directory: `/e/08/erthch01/` (hardcoded in several places)
- Data directories: `$HOME/data/intel/`, `$HOME/data/accuwx_*/`
- Log directories: `$HOME/logs/*/` and `/e/08/erthch01/logs/`
- Web deployment: Files served from `rcity2.cottay.net:/srv/www/earthcast/`