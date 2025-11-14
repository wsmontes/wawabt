#!/bin/bash
# Monitor sentiment analysis progress

CHECKPOINT_FILE="sentiment_checkpoint.json"
LOG_FILE="sentiment_mass_run.log"

echo "======================================================================"
echo " SENTIMENT ANALYSIS PROGRESS MONITOR"
echo "======================================================================"
echo ""

# Check if process is running
if ps aux | grep -v grep | grep "analyze_sentiment_mass.py" > /dev/null; then
    echo "✅ Process is running"
    PID=$(ps aux | grep -v grep | grep "analyze_sentiment_mass.py" | awk '{print $2}')
    echo "   PID: $PID"
else
    echo "⚠️  Process is NOT running"
fi

echo ""

# Show checkpoint stats
if [ -f "$CHECKPOINT_FILE" ]; then
    echo "📊 Checkpoint Statistics:"
    echo ""
    python3 -c "
import json
with open('$CHECKPOINT_FILE', 'r') as f:
    data = json.load(f)
    stats = data['stats']
    processed = len(data['processed'])
    failed = len(data['failed'])
    total = stats['total_sources']
    
    print(f'  Sources:')
    print(f'    Total:        {total}')
    print(f'    Processed:    {processed} ({processed/total*100:.1f}%)')
    print(f'    Pending:      {total-processed}')
    print(f'    Failed:       {failed}')
    print(f'')
    print(f'  Articles:')
    print(f'    Found:        {stats[\"total_articles\"]:,}')
    print(f'    Analyzed:     {stats[\"total_analyzed\"]:,}')
    print(f'')
    if stats['total_analyzed'] > 0:
        print(f'  Sentiment:')
        print(f'    Positive:     {stats[\"positive\"]:,} ({stats[\"positive\"]/stats[\"total_analyzed\"]*100:.1f}%)')
        print(f'    Negative:     {stats[\"negative\"]:,} ({stats[\"negative\"]/stats[\"total_analyzed\"]*100:.1f}%)')
        print(f'    Neutral:      {stats[\"neutral\"]:,} ({stats[\"neutral\"]/stats[\"total_analyzed\"]*100:.1f}%)')
    print(f'')
    print(f'  Started:       {data[\"started_at\"]}')
    print(f'  Last update:   {data[\"last_update\"]}')
"
else
    echo "⚠️  Checkpoint file not found"
fi

echo ""
echo "======================================================================"
echo " RECENT LOG ENTRIES (last 15 lines)"
echo "======================================================================"

if [ -f "$LOG_FILE" ]; then
    tail -n 15 "$LOG_FILE"
else
    echo "⚠️  Log file not found"
fi

echo ""
echo "======================================================================"
echo " Commands:"
echo "   watch -n 5 ./monitor_sentiment.sh    # Auto-refresh every 5 seconds"
echo "   python analyze_sentiment_mass.py --summary  # Show full summary"
echo "   tail -f sentiment_mass_run.log       # Follow log in real-time"
echo "======================================================================"
