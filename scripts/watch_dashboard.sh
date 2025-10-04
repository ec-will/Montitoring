#!/bin/bash

# Auto-refreshing dashboard 
echo "Starting EarthCast HPC Dashboard Monitor..."
echo "Press Ctrl+C to exit"
echo ""

watch -c -n 30 "$HOME/monitoring/scripts/dashboard_v9.sh"
