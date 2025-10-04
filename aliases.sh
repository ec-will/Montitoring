#!/bin/bash

# EarthCast HPC Dashboard Aliases v19
# Fixed upcoming jobs calculation to properly handle day transitions

# Dashboard commands
alias dashboard='$HOME/monitoring/scripts/dashboard_v19.sh'
alias hpc-status='$HOME/monitoring/scripts/dashboard_v19.sh'
alias dashboard-watch='watch -c -n 30 $HOME/monitoring/scripts/dashboard_v19.sh'
alias monitor='watch -c -n 30 $HOME/monitoring/scripts/dashboard_v19.sh'

# Log checking aliases
alias check-wrf='ls -la $HOME/logs/wrf/run_master.global* | tail -5'
alias check-mrms='ls -la $HOME/logs/mrms/wget_mrms_QCEchoHgt* | tail -5'
alias check-hiresw='ls -la $HOME/logs/hiresw/master_hiresw_seq* | tail -5'
alias check-drone='ls -la $HOME/logs/wrf/drone_wx_seq* | tail -5'

# System status commands
alias pbs-status='qstat -u erthch01'
alias disk-status='df -h $HOME'
alias log-activity='find $HOME/logs -name "*.log" -mmin -60 | wc -l'

echo "EarthCast HPC Dashboard aliases loaded!"
echo "Commands available:"
echo "  dashboard       - Show current status with upcoming jobs (fixed day transitions)"
echo "  dashboard-watch - Auto-refresh every 30 seconds"
echo "  hpc-status      - Same as dashboard"
echo "  monitor         - Same as dashboard-watch"
echo ""
echo "Log checking:"
echo "  check-wrf, check-mrms, check-hiresw, check-drone"
echo ""
echo "System status:"
echo "  pbs-status, disk-status, log-activity"
