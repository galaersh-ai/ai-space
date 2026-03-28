#!/bin/bash
# setup-cron.sh - Setup cron job for AI Space agent
#
# Usage: ./setup-cron.sh [interval]
#   interval: 5, 10, 15, 30 (minutes) - default: 15

INTERVAL=${1:-15}
AI_HOME="/root/ai_space"
SCRIPT_PATH="$AI_HOME/core.py"
LOG_PATH="$AI_HOME/logs/cron.log"

# Validate interval
if [[ ! "$INTERVAL" =~ ^(5|10|15|30)$ ]]; then
    echo "Invalid interval: $INTERVAL"
    echo "Usage: ./setup-cron.sh [5|10|15|30]"
    exit 1
fi

# Create cron entry
CRON_ENTRY="*/$INTERVAL * * * * cd $AI_HOME && /usr/bin/python3 $SCRIPT_PATH >> $LOG_PATH 2>&1"

# Check if already exists
if crontab -l 2>/dev/null | grep -q "core.py"; then
    echo "Removing existing cron job..."
    crontab -l | grep -v "core.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "Cron job installed:"
echo "  Interval: every $INTERVAL minutes"
echo "  Command: python3 $SCRIPT_PATH"
echo "  Log: $LOG_PATH"
echo ""
echo "Current crontab:"
crontab -l | grep "core.py"
echo ""
echo "To remove: crontab -e (and delete the line)"
echo "To check logs: tail -f $LOG_PATH"
