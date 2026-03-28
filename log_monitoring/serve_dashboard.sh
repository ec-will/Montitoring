#!/bin/bash

# Transfer Log Dashboard Server
# This script updates the JSON data and serves the dashboard

set -e

echo "=== Transfer Log Dashboard Server ==="
echo

# Check if transfer.log exists
if [ ! -f "transfer.log" ]; then
    echo "❌ Error: transfer.log not found"
    echo "Please ensure transfer.log is in the current directory"
    exit 1
fi

# Parse the transfer log
echo "📊 Parsing transfer.log..."
python3 parse_transfers.py --summary

if [ $? -ne 0 ]; then
    echo "❌ Error parsing transfer log"
    exit 1
fi

# Check if JSON was created
if [ ! -f "transfers.json" ]; then
    echo "❌ Error: transfers.json was not created"
    exit 1
fi

echo "✅ JSON data updated successfully"
echo

# Check if dashboard HTML exists
if [ ! -f "transfers.html" ]; then
    echo "❌ Error: transfers.html not found"
    exit 1
fi

# Find available port
PORT=8080
while lsof -i :$PORT >/dev/null 2>&1; do
    PORT=$((PORT + 1))
    if [ $PORT -gt 8090 ]; then
        echo "❌ Error: No available ports in range 8080-8090"
        exit 1
    fi
done

echo "🌐 Starting web server on port $PORT..."
echo "Dashboard will be available at: http://127.0.0.1:$PORT/transfers.html"
echo

# Kill any existing Python servers
pkill -f "python3 -m http.server" 2>/dev/null || true
sleep 1

# Start the HTTP server
python3 -m http.server $PORT --bind 127.0.0.1 &
SERVER_PID=$!

echo "✅ Server started (PID: $SERVER_PID)"
echo

# Wait a moment for server to start
sleep 2

# Open dashboard in browser
if command -v open >/dev/null 2>&1; then
    echo "🔗 Opening dashboard in browser..."
    open "http://127.0.0.1:$PORT/transfers.html"
elif command -v xdg-open >/dev/null 2>&1; then
    echo "🔗 Opening dashboard in browser..."
    xdg-open "http://127.0.0.1:$PORT/transfers.html"
else
    echo "🔗 Please open http://127.0.0.1:$PORT/transfers.html in your browser"
fi

echo
echo "📋 Dashboard Features:"
echo "  • View transfer sessions grouped by PID"
echo "  • Filter by log type (INFO, SUCCESS, ERROR)"
echo "  • Filter by transfer method (scp, cp, rsync)"
echo "  • Search files, destinations, and messages"
echo "  • Click session headers to expand/collapse"
echo "  • Auto-refresh every 5 minutes"
echo
echo "⏹️  Press Ctrl+C to stop the server"

# Keep script running and handle Ctrl+C
trap 'echo; echo "🛑 Stopping server..."; kill $SERVER_PID 2>/dev/null; echo "✅ Server stopped"; exit 0' INT

# Wait for server process
wait $SERVER_PID