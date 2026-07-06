#!/bin/bash
# start_scheduler.sh - Start Celery for email scheduling

echo "🚀 Starting Celery Worker and Beat Scheduler..."
echo ""
echo "This script starts 2 processes:"
echo "  1. Celery Worker (processes tasks)"
echo "  2. Celery Beat (scheduler - runs every minute)"
echo ""
echo "Keep both running in background or in separate terminals."
echo ""

cd /home/didar-ahmed/Desktop/RevriBB

echo "Starting Celery Worker..."
celery -A project_root worker -l info &
WORKER_PID=$!

sleep 2

echo ""
echo "Starting Celery Beat..."
celery -A project_root beat -l info &
BEAT_PID=$!

echo ""
echo "✅ Services started:"
echo "   Worker PID: $WORKER_PID"
echo "   Beat PID: $BEAT_PID"
echo ""
echo "📧 Emails will now send automatically at scheduled times."
echo "Press Ctrl+C to stop all services."

wait
