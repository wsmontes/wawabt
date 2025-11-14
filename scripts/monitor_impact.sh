#!/bin/bash
# Monitor news-market impact analysis

echo "======================================================================"
echo " NEWS-MARKET IMPACT ANALYSIS MONITOR"
echo "======================================================================"
echo ""

# Check if process is running
if ps aux | grep -v grep | grep "analyze_news_market_impact.py" > /dev/null; then
    echo "✅ Process is running"
    PID=$(ps aux | grep -v grep | grep "analyze_news_market_impact.py" | awk '{print $2}')
    echo "   PID: $PID"
    
    # Show CPU and memory usage
    ps -p $PID -o %cpu,%mem,etime | tail -1 | while read cpu mem time; do
        echo "   CPU: ${cpu}%"
        echo "   Memory: ${mem}%"
        echo "   Runtime: ${time}"
    done
else
    echo "⚠️  Process is NOT running"
fi

echo ""
echo "======================================================================"
echo " RECENT LOG ENTRIES (last 20 lines)"
echo "======================================================================"

if [ -f "impact_analysis.log" ]; then
    tail -n 20 impact_analysis.log
else
    echo "⚠️  Log file not found"
fi

echo ""
echo "======================================================================"
echo " FILE SIZES"
echo "======================================================================"

if [ -f "news_market_impact_report.json" ]; then
    echo "JSON Report: $(du -h news_market_impact_report.json | cut -f1)"
fi

if [ -f "NEWS_MARKET_IMPACT_REPORT.md" ]; then
    echo "Markdown Report: $(du -h NEWS_MARKET_IMPACT_REPORT.md | cut -f1)"
fi

echo ""
echo "======================================================================"
echo " Commands:"
echo "   watch -n 5 ./monitor_impact.sh    # Auto-refresh every 5 seconds"
echo "   tail -f impact_analysis.log       # Follow log in real-time"
echo "   pkill -f analyze_news_market      # Stop analysis"
echo "======================================================================"
