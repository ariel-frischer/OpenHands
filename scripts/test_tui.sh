#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Set log file with timestamp
LOG_FILE="logs/tui_test_$(date +%Y%m%d_%H%M%S).log"

echo "Starting TUI test with logging to: $LOG_FILE"
echo "TUI will run for 10 seconds with debug layout and logging..."

# Run TUI with timeout and capture all output
timeout 10s poetry run python -m openhands.tui.main \
    --tui-debug-layout \
    --tui-log-level DEBUG \
    --tui-timeout 8 \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "TUI test completed. Log file: $LOG_FILE"
echo "Log file size: $(wc -l < "$LOG_FILE") lines"
echo ""
echo "Last 20 lines of log:"
tail -20 "$LOG_FILE" 