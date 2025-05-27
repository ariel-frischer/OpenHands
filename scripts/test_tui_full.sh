#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Set log file with timestamp
LOG_FILE="logs/tui_full_test_$(date +%Y%m%d_%H%M%S).log"

echo "Starting TUI FULL test with logging to: $LOG_FILE"
echo "TUI will run for 15 seconds with full session creation..."

# Run TUI with timeout and capture all output (no debug layout)
timeout 15s poetry run python -m openhands.tui.main \
    --tui-log-level DEBUG \
    --tui-timeout 12 \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "TUI full test completed. Log file: $LOG_FILE"
echo "Log file size: $(wc -l < "$LOG_FILE") lines"
echo ""
echo "Last 30 lines of log:"
tail -30 "$LOG_FILE" 