#!/bin/bash
# Monitor da pipeline de trading

DB="data/market_data.duckdb"

if [ ! -f "$DB" ]; then
    echo "❌ Database não encontrado: $DB"
    exit 1
fi

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================="
echo "   Pipeline Trading Monitor"
echo -e "===================================${NC}"
echo ""

# Status das Notícias
echo -e "${YELLOW}📰 Status das Notícias${NC}"
duckdb $DB -box -c "
SELECT 
    status,
    COUNT(*) as count,
    MAX(published_at) as last_published
FROM news_raw
GROUP BY status
"
echo ""

# Sentimentos Recentes
echo -e "${YELLOW}💭 Sentimentos Recentes (Top 10)${NC}"
duckdb $DB -box -c "
SELECT 
    symbol,
    sentiment,
    ROUND(sentiment_score, 3) as score,
    ROUND(confidence, 3) as conf,
    strftime(analyzed_at, '%Y-%m-%d %H:%M') as time
FROM news_by_symbol
ORDER BY analyzed_at DESC
LIMIT 10
"
echo ""

# Alertas Ativos
echo -e "${YELLOW}🚨 Alertas Ativos${NC}"
ALERTS=$(duckdb $DB -c "SELECT COUNT(*) FROM realtime_alerts WHERE status='active'" | tail -1)
if [ "$ALERTS" -gt 0 ]; then
    duckdb $DB -box -c "
    SELECT 
        symbol,
        signal_type,
        ROUND(signal_strength, 3) as strength,
        ROUND(confidence, 3) as conf,
        strftime(generated_at, '%H:%M') as time,
        exchange
    FROM realtime_alerts
    WHERE status = 'active'
    ORDER BY signal_strength DESC
    LIMIT 15
    "
else
    echo -e "${RED}Nenhum alerta ativo${NC}"
fi
echo ""

# Posições Abertas
echo -e "${YELLOW}📊 Posições Abertas${NC}"
POSITIONS=$(duckdb $DB -c "SELECT COUNT(*) FROM paper_trades WHERE status='open'" | tail -1)
if [ "$POSITIONS" -gt 0 ]; then
    duckdb $DB -box -c "
    SELECT 
        symbol,
        side,
        ROUND(quantity, 4) as qty,
        ROUND(entry_price, 2) as entry,
        ROUND(stop_loss, 2) as sl,
        ROUND(take_profit, 2) as tp,
        ROUND((julianday('now') - julianday(opened_at)) * 24, 1) || 'h' as open_time,
        exchange
    FROM paper_trades
    WHERE status = 'open'
    ORDER BY opened_at DESC
    "
else
    echo -e "${GREEN}Nenhuma posição aberta${NC}"
fi
echo ""

# Performance do Portfolio
echo -e "${YELLOW}💰 Performance do Portfolio${NC}"
duckdb $DB -box -c "
SELECT 
    exchange,
    ROUND(total_value, 2) as value,
    ROUND(cash, 2) as cash,
    open_positions as positions,
    total_trades as trades,
    ROUND(win_rate * 100, 1) || '%' as win_rate,
    ROUND(total_pnl, 2) as pnl,
    ROUND(sharpe_ratio, 2) as sharpe,
    strftime(updated_at, '%Y-%m-%d %H:%M') as updated
FROM portfolio_state
ORDER BY exchange
"
echo ""

# Trades Recentes Fechados
echo -e "${YELLOW}📈 Últimos 10 Trades Fechados${NC}"
CLOSED=$(duckdb $DB -c "SELECT COUNT(*) FROM paper_trades WHERE status='closed'" | tail -1)
if [ "$CLOSED" -gt 0 ]; then
    duckdb $DB -box -c "
    SELECT 
        symbol,
        side,
        ROUND(pnl, 2) as pnl,
        ROUND(pnl_pct * 100, 2) || '%' as pnl_pct,
        exit_reason,
        ROUND(holding_period_hours, 1) || 'h' as duration,
        strftime(closed_at, '%m-%d %H:%M') as closed,
        exchange
    FROM paper_trades
    WHERE status = 'closed'
    ORDER BY closed_at DESC
    LIMIT 10
    "
else
    echo -e "${YELLOW}Nenhum trade fechado ainda${NC}"
fi
echo ""

# Resumo
echo -e "${BLUE}==================================="
echo "   Resumo"
echo -e "===================================${NC}"
echo -e "Notícias coletadas: ${GREEN}$(duckdb $DB -c "SELECT COUNT(*) FROM news_raw" | tail -1)${NC}"
echo -e "Alertas ativos: ${YELLOW}$ALERTS${NC}"
echo -e "Posições abertas: ${BLUE}$POSITIONS${NC}"
echo -e "Trades fechados: ${GREEN}$CLOSED${NC}"

# Total P&L
TOTAL_PNL=$(duckdb $DB -c "SELECT COALESCE(ROUND(SUM(total_pnl), 2), 0) FROM portfolio_state" | tail -1)
if (( $(echo "$TOTAL_PNL > 0" | bc -l) )); then
    echo -e "P&L Total: ${GREEN}+\$$TOTAL_PNL${NC}"
elif (( $(echo "$TOTAL_PNL < 0" | bc -l) )); then
    echo -e "P&L Total: ${RED}\$$TOTAL_PNL${NC}"
else
    echo -e "P&L Total: \$0.00"
fi

echo ""
echo "📊 Para atualizar: watch -n 30 ./scripts/monitor.sh"
echo "📝 Ver logs: tail -f logs/pipeline_\$(date +%Y%m%d).log"
echo ""
