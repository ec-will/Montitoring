#!/bin/bash
#
# Add this snippet to your existing deployment script (e.g., update_dashboard_cron.sh)
# This generates the login jobs timeline HTML and pushes it to the web server
#

# Login Node Jobs Timeline
echo "Generating login jobs timeline..."
cd $HOME/monitoring/web_dashboard

# Generate the HTML from JSON
python3 web_server_login_timeline_plot.py dashboard_login_jobs.json login_jobs_timeline.html

if [ $? -eq 0 ]; then
    echo "Login jobs timeline generated successfully"
    
    # Push to web server
    echo "Pushing login jobs timeline to web server..."
    scp login_jobs_timeline.html rcity2.cottay.net:/srv/www/earthcast/
    
    if [ $? -eq 0 ]; then
        echo "Login jobs timeline deployed successfully"
    else
        echo "Error: Failed to push login jobs timeline to web server"
    fi
else
    echo "Error: Failed to generate login jobs timeline"
fi
