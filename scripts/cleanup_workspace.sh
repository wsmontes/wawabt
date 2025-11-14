#!/bin/bash
# Workspace cleanup script for WawaBackTrader
# Run weekly to keep workspace organized

set -e

echo "🧹 WawaBackTrader Workspace Cleanup"
echo "===================================="
echo ""

# Move stray logs
echo "📋 Moving stray logs..."
moved_logs=0
for log in *.log; do
    [ -f "$log" ] && mv "$log" logs/ && ((moved_logs++))
done
[ $moved_logs -gt 0 ] && echo "✅ Moved $moved_logs log file(s)" || echo "✅ No stray logs"

# Clean temp directory
echo ""
echo "🗑️  Cleaning temp directory..."
if [ -d "temp" ]; then
    temp_files=$(find temp/ -type f | wc -l | tr -d ' ')
    rm -rf temp/*
    [ $temp_files -gt 0 ] && echo "✅ Removed $temp_files temporary file(s)" || echo "✅ Temp already clean"
else
    echo "⚠️  temp/ directory not found"
fi

# Remove old versioned files
echo ""
echo "🔄 Removing old versions..."
old_files=$(ls *_OLD_* *_v[0-9].log *_v[0-9][0-9].log 2>/dev/null | wc -l | tr -d ' ')
rm -f *_OLD_* *_v[0-9].log *_v[0-9][0-9].log 2>/dev/null
[ $old_files -gt 0 ] && echo "✅ Removed $old_files old version(s)" || echo "✅ No old versions found"

# Remove temporary test scripts (only in root)
echo ""
echo "🧪 Removing temporary test scripts..."
test_scripts=$(ls test_*.py check_*.py validate_*.py import_*.py 2>/dev/null | wc -l | tr -d ' ')
rm -f test_*.py check_*.py validate_*.py import_*.py 2>/dev/null
[ $test_scripts -gt 0 ] && echo "✅ Removed $test_scripts test script(s)" || echo "✅ No test scripts found"

# Remove old logs (30+ days)
echo ""
echo "📅 Removing logs older than 30 days..."
if [ -d "logs" ]; then
    old_logs=$(find logs/ -name "*.log" -mtime +30 2>/dev/null | wc -l | tr -d ' ')
    find logs/ -name "*.log" -mtime +30 -delete 2>/dev/null
    [ $old_logs -gt 0 ] && echo "✅ Removed $old_logs old log(s)" || echo "✅ No old logs to remove"
else
    echo "⚠️  logs/ directory not found"
fi

# Remove nohup.out if exists
echo ""
echo "🚫 Removing nohup.out..."
[ -f "nohup.out" ] && rm nohup.out && echo "✅ Removed nohup.out" || echo "✅ No nohup.out found"

# Optional: Clean old backtest results (keep last 20)
echo ""
echo "📊 Cleaning old backtest results (keeping last 20)..."
if [ -d "results/backtest" ]; then
    cd results/backtest
    backtest_count=$(ls -1 results_*.json 2>/dev/null | wc -l | tr -d ' ')
    if [ $backtest_count -gt 20 ]; then
        old_backtests=$((backtest_count - 20))
        ls -t results_*.json | tail -n +21 | xargs rm -f 2>/dev/null
        echo "✅ Removed $old_backtests old backtest(s)"
    else
        echo "✅ Backtest results within limit ($backtest_count files)"
    fi
    cd ../..
else
    echo "⚠️  results/backtest/ directory not found"
fi

# Show disk usage summary
echo ""
echo "📊 Disk Usage Summary:"
echo "====================="
[ -d "data" ] && echo "  data/:    $(du -sh data/ 2>/dev/null | cut -f1)" || echo "  data/:    N/A"
[ -d "logs" ] && echo "  logs/:    $(du -sh logs/ 2>/dev/null | cut -f1)" || echo "  logs/:    N/A"
[ -d "results" ] && echo "  results/: $(du -sh results/ 2>/dev/null | cut -f1)" || echo "  results/: N/A"
[ -d "temp" ] && echo "  temp/:    $(du -sh temp/ 2>/dev/null | cut -f1)" || echo "  temp/:    N/A"

# Show file counts
echo ""
echo "📁 File Counts:"
echo "==============="
[ -d "logs" ] && echo "  Logs:          $(find logs/ -name "*.log" 2>/dev/null | wc -l | tr -d ' ')" || echo "  Logs:          N/A"
[ -d "results/backtest" ] && echo "  Backtests:     $(find results/backtest/ -name "*.json" 2>/dev/null | wc -l | tr -d ' ')" || echo "  Backtests:     N/A"
[ -d "results/analysis" ] && echo "  Analysis:      $(find results/analysis/ -name "*.json" 2>/dev/null | wc -l | tr -d ' ')" || echo "  Analysis:      N/A"
[ -d "data/market" ] && echo "  Market files:  $(find data/market/ -name "*.parquet" 2>/dev/null | wc -l | tr -d ' ')" || echo "  Market files:  N/A"

echo ""
echo "✨ Cleanup complete!"
echo ""
echo "💡 Next steps:"
echo "  - Review results/ directory if needed"
echo "  - Check logs/ for any important information"
echo "  - Run 'git status' to verify no data files staged"
