# EarthCast HPC Monitoring Dashboard

A comprehensive monitoring dashboard for EarthCast HPC weather forecasting operations, providing real-time status of WRF model runs, PBS job queues, and system health.

## Features

- **Intelligent WRF Monitoring**: Tracks Global WRF, AccuWeather Asia, and AccuWeather Europe workflows
- **Success/Failure Detection**: Analyzes log contents and wrfout file counts for accurate status
- **Real-Time Systems**: Monitors MRMS radar data and drone weather processing
- **PBS Job Integration**: Shows active jobs with full script names and resource usage
- **Waiting State Intelligence**: Distinguishes between data delays and actual failures
- **12-Hour Job Forecasting**: Displays upcoming scheduled jobs
- **System Health Metrics**: Disk usage, log activity, and queue status
- **Color-Coded Display**: Visual status indicators with colored legend

## Installation

```bash
# Load the dashboard aliases
source $HOME/monitoring/aliases.sh

# Run the dashboard
dashboard

# Auto-refresh monitoring (30-second intervals)
monitor
```

## Dashboard Versions

- **v1-v16**: Development iterations with incremental features
- **v17**: Added wrfout file counting for WRF workflows
- **v18**: Fixed AccuWeather Europe path (data/accuwx_plus)
- **Current**: v18 with complete WRF file count monitoring

## Commands

- `dashboard` - Show current status
- `monitor` - Auto-refresh every 30 seconds  
- `hpc-status` - Same as dashboard
- `check-wrf` - Check recent WRF logs
- `check-mrms` - Check MRMS radar logs
- `pbs-status` - Show PBS queue status

## Configuration

The dashboard automatically detects:
- WRF output files in data directories
- Log file timestamps for last run detection
- PBS job status and resource usage
- System health metrics

## Directory Structure

- `scripts/` - Dashboard versions and implementations
- `aliases.sh` - Command aliases and configuration
- `README.md` - This documentation

## Status Indicators

- 🟢 **●●● Green** - Success/Running normally
- 🟡 **●●○ Yellow** - Warning/Waiting for data
- 🟠 **●○○ Orange** - Error/Failed
- 🔴 **○○○ Red** - Critical issues
- 🔵 **◐◐◐ Blue** - Scheduled jobs

## WRF Output Monitoring

The dashboard counts wrfout files to detect incomplete runs:
- **Global WRF**: ~37 files for 36-hour runs
- **AccuWeather Asia**: ~33 files for regional runs
- **AccuWeather Europe**: ~33 files for regional runs

Low file counts indicate premature termination even if exit status appears successful.

## Author

**ect-will** - EarthCast Technologies HPC Operations
