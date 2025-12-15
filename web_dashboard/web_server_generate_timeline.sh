#!/bin/bash
# Web Server Script to Generate Cluster Usage Timeline
# Should be run on rcity2.cottay.net after JSON file is updated

SCRIPT_DIR="/srv/www/earthcast"
JSON_FILE="$SCRIPT_DIR/dashboard_cluster_usage.json"
HTML_FILE="$SCRIPT_DIR/cluster_usage_timeline.html"
PYTHON_SCRIPT="$SCRIPT_DIR/web_server_timeline_plot.py"

# Check if JSON file exists and was recently updated
if [[ ! -f "$JSON_FILE" ]]; then
    echo "Error: $JSON_FILE not found"
    exit 1
fi

# Check if the JSON file is less than 2 hours old
if [[ $(find "$JSON_FILE" -mmin -120 | wc -l) -eq 0 ]]; then
    echo "Warning: $JSON_FILE is more than 2 hours old"
fi

# Generate the timeline plot
echo "Generating cluster usage timeline..."
cd "$SCRIPT_DIR"

if python3 "$PYTHON_SCRIPT" "$JSON_FILE" "$HTML_FILE"; then
    echo "Successfully generated $HTML_FILE"
    echo "File size: $(ls -lh "$HTML_FILE" | awk '{print $5}')"
    
    # Make sure it's web-accessible
    chmod 644 "$HTML_FILE"
    
else
    echo "Error: Failed to generate timeline plot"
    exit 1
fi
