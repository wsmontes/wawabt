#!/bin/bash
# Monitor the historical data population progress

LOG_FILE="historical_population.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Log file not found: $LOG_FILE"
    exit 1
fi

echo "📊 Historical Data Population Monitor"
echo "======================================"
echo ""

# Check if process is still running
if pgrep -f "populate_historical_data.py" > /dev/null; then
    echo "✅ Process is running"
else
    echo "⚠️  Process is not running (may have completed)"
fi

echo ""

# Count progress
CRYPTO_SUCCESS=$(grep -c "CRYPTO.*✓.*records" "$LOG_FILE" 2>/dev/null || echo 0)
STOCK_SUCCESS=$(grep -c "STOCK.*✓.*records" "$LOG_FILE" 2>/dev/null || echo 0)
CRYPTO_FAILED=$(grep -c "CRYPTO.*❌" "$LOG_FILE" 2>/dev/null || echo 0)
STOCK_FAILED=$(grep -c "STOCK.*❌" "$LOG_FILE" 2>/dev/null || echo 0)

echo "📈 Progress:"
echo "   Crypto: $CRYPTO_SUCCESS successful, $CRYPTO_FAILED failed"
echo "   Stocks: $STOCK_SUCCESS successful, $STOCK_FAILED failed"

echo ""
echo "📄 Last 10 lines:"
echo "----------------------------------------"
tail -10 "$LOG_FILE"
echo "----------------------------------------"

echo ""
echo "To see full log: tail -f $LOG_FILE"
