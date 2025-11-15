# 📖 Exemplos Práticos de Uso

## Cenário 1: Setup e Primeira Execução

```bash
# 1. Ativar ambiente
cd ~/Documents/GitHub/wawabt
source venv/bin/activate

# 2. Setup completo
./scripts/setup_pipeline.sh

# 3. Configurar APIs
nano config/paper_trading.json
# Preencher api_key e api_secret para Alpaca e Binance

# 4. Teste rápido
./scripts/test_pipeline.sh

# 5. Executar uma vez
python engines/pipeline_scheduler.py --test

# 6. Ver resultados
./scripts/status.py
```

**Output esperado:**
```
📰 Notícias: 150 coletadas
💭 Sentimentos: 120 analisados
🚨 Alertas: 5 ativos
📊 Posições: 0 abertas (primeira execução)
```

---

## Cenário 2: Coletar Notícias Manualmente

```bash
# Executar news collector
python engines/news_collector_pipeline.py

# Ver o que foi coletado
duckdb data/market_data.duckdb -box -c "
SELECT 
    source,
    COUNT(*) as count,
    MIN(published_at) as oldest,
    MAX(published_at) as newest
FROM news_raw
GROUP BY source
ORDER BY count DESC
"
```

**Output esperado:**
```
┌──────────────────┬───────┬─────────────────────┬─────────────────────┐
│     source       │ count │       oldest        │       newest        │
├──────────────────┼───────┼─────────────────────┼─────────────────────┤
│ Yahoo Finance    │    45 │ 2025-11-14 08:00:00 │ 2025-11-14 14:30:00 │
│ Bloomberg        │    38 │ 2025-11-14 09:15:00 │ 2025-11-14 14:25:00 │
│ Reuters          │    32 │ 2025-11-14 10:00:00 │ 2025-11-14 14:20:00 │
│ Alpaca News API  │    25 │ 2025-11-14 11:00:00 │ 2025-11-14 14:30:00 │
└──────────────────┴───────┴─────────────────────┴─────────────────────┘
```

---

## Cenário 3: Analisar Sentimentos

```bash
# Executar sentiment pipeline
python engines/sentiment_pipeline.py

# Ver distribuição de sentimentos
duckdb data/market_data.duckdb -box -c "
SELECT 
    sentiment,
    COUNT(*) as count,
    ROUND(AVG(confidence), 3) as avg_confidence,
    ROUND(AVG(sentiment_score), 3) as avg_score
FROM news_sentiment
GROUP BY sentiment
ORDER BY count DESC
"
```

**Output esperado:**
```
┌───────────┬───────┬────────────────┬───────────┐
│ sentiment │ count │ avg_confidence │ avg_score │
├───────────┼───────┼────────────────┼───────────┤
│ neutral   │    65 │          0.856 │     0.000 │
│ positive  │    35 │          0.892 │     0.652 │
│ negative  │    20 │          0.871 │    -0.598 │
└───────────┴───────┴────────────────┴───────────┘
```

---

## Cenário 4: Gerar Alertas de Trading

```bash
# Executar alert manager
python engines/realtime_alert_manager.py

# Ver top alertas
duckdb data/market_data.duckdb -box -c "
SELECT 
    symbol,
    signal_type,
    ROUND(signal_strength, 3) as strength,
    ROUND(sentiment_score, 3) as score,
    ROUND(confidence, 3) as conf,
    news_count,
    exchange
FROM realtime_alerts
WHERE status = 'active'
ORDER BY signal_strength DESC
LIMIT 10
"
```

**Output esperado:**
```
┌────────┬─────────────┬──────────┬─────────┬───────┬────────────┬──────────┐
│ symbol │ signal_type │ strength │  score  │ conf  │ news_count │ exchange │
├────────┼─────────────┼──────────┼─────────┼───────┼────────────┼──────────┤
│ NVDA   │ BUY         │    0.856 │   0.712 │ 0.912 │          8 │ alpaca   │
│ AAPL   │ BUY         │    0.743 │   0.621 │ 0.887 │          6 │ alpaca   │
│ BTCUSD │ BUY         │    0.698 │   0.582 │ 0.901 │         12 │ binance  │
│ TSLA   │ SELL        │    0.612 │  -0.542 │ 0.856 │          5 │ alpaca   │
│ ETHUSD │ BUY         │    0.589 │   0.491 │ 0.871 │          9 │ binance  │
└────────┴─────────────┴──────────┴─────────┴───────┴────────────┴──────────┘
```

---

## Cenário 5: Executar Trades (Paper Trading)

```bash
# ATENÇÃO: Vai executar trades reais em paper trading!

# Executar signal execution
python engines/signal_execution.py

# Ver trades abertos
duckdb data/market_data.duckdb -box -c "
SELECT 
    symbol,
    side,
    ROUND(quantity, 4) as qty,
    ROUND(entry_price, 2) as entry,
    ROUND(stop_loss, 2) as sl,
    ROUND(take_profit, 2) as tp,
    exchange,
    strftime(opened_at, '%H:%M') as time
FROM paper_trades
WHERE status = 'open'
ORDER BY opened_at DESC
"
```

**Output esperado:**
```
┌────────┬──────┬─────────┬────────┬────────┬─────────┬──────────┬───────┐
│ symbol │ side │   qty   │ entry  │   sl   │   tp    │ exchange │ time  │
├────────┼──────┼─────────┼────────┼────────┼─────────┼──────────┼───────┤
│ NVDA   │ BUY  │ 15.0000 │ 485.32 │ 475.61 │ 509.59  │ alpaca   │ 14:35 │
│ AAPL   │ BUY  │ 52.0000 │ 178.45 │ 174.88 │ 187.37  │ alpaca   │ 14:33 │
│ BTCUSD │ BUY  │  0.1250 │ 37250  │ 36133  │ 40230   │ binance  │ 14:31 │
└────────┴──────┴─────────┴────────┴────────┴─────────┴──────────┴───────┘
```

---

## Cenário 6: Monitorar Performance

```bash
# Executar performance tracker
python engines/performance_tracker.py

# Ver P&L das posições
duckdb data/market_data.duckdb -box -c "
SELECT 
    symbol,
    side,
    ROUND(entry_price, 2) as entry,
    ROUND(exit_price, 2) as exit,
    ROUND(pnl, 2) as pnl,
    ROUND(pnl_pct * 100, 2) || '%' as pnl_pct,
    exit_reason,
    ROUND(holding_period_hours, 1) || 'h' as duration
FROM paper_trades
WHERE status = 'closed'
ORDER BY closed_at DESC
LIMIT 10
"
```

**Output esperado:**
```
┌────────┬──────┬────────┬────────┬─────────┬─────────┬─────────────┬──────────┐
│ symbol │ side │ entry  │  exit  │   pnl   │ pnl_pct │ exit_reason │ duration │
├────────┼──────┼────────┼────────┼─────────┼─────────┼─────────────┼──────────┤
│ TSLA   │ SELL │ 245.60 │ 251.30 │ -142.50 │  -5.80% │ stop_loss   │     3.2h │
│ MSFT   │ BUY  │ 368.20 │ 372.15 │  197.50 │  +5.38% │ take_profit │     4.8h │
│ ETHUSD │ BUY  │ 2050.0 │ 2163.0 │  226.00 │  +5.51% │ take_profit │     6.1h │
│ AAPL   │ BUY  │ 178.45 │ 179.82 │   71.24 │  +3.85% │ manual      │     2.5h │
└────────┴──────┴────────┴────────┴─────────┴─────────┴─────────────┴──────────┘
```

---

## Cenário 7: Executar Pipeline Completa (Produção)

```bash
# Executar scheduler em background
nohup python engines/pipeline_scheduler.py > scheduler.out 2>&1 &

# Ver logs em tempo real
tail -f logs/pipeline_$(date +%Y%m%d).log

# Monitorar a cada 30s
watch -n 30 ./scripts/status.py

# Ver próximas execuções (após iniciar)
# Ctrl+C para parar
python engines/pipeline_scheduler.py
```

**Output de logs esperado:**
```
2025-11-14 14:30:15 - INFO - NewsCollector: Collected 45 news, saved 38 (7 duplicates)
2025-11-14 14:31:10 - INFO - SentimentPipeline: Analyzed 38 news, 15 positive, 8 negative, 15 neutral
2025-11-14 14:32:05 - INFO - AlertManager: Generated 5 alerts (3 BUY, 2 SELL)
2025-11-14 14:33:00 - INFO - SignalExecution: Executed 3 trades (2 alpaca, 1 binance)
2025-11-14 14:33:45 - INFO - PerformanceTracker: Monitoring 5 positions, total P&L: +$324.75
```

---

## Cenário 8: Análise de Resultados

```bash
# Dashboard completo
./scripts/monitor.sh
```

**Output esperado:**
```
===================================
   Pipeline Trading Monitor
===================================

📰 Status das Notícias
┌───────────┬───────┬─────────────────────┐
│  status   │ count │   last_published    │
├───────────┼───────┼─────────────────────┤
│ processed │   180 │ 2025-11-14 14:30:00 │
│ pending   │    15 │ 2025-11-14 14:32:00 │
└───────────┴───────┴─────────────────────┘

💭 Sentimentos Recentes (Top 10)
┌────────┬───────────┬────────┬───────┬─────────────────┐
│ symbol │ sentiment │ score  │ conf  │      time       │
├────────┼───────────┼────────┼───────┼─────────────────┤
│ NVDA   │ positive  │  0.712 │ 0.912 │ 2025-11-14 14:30│
│ AAPL   │ positive  │  0.621 │ 0.887 │ 2025-11-14 14:28│
│ BTCUSD │ positive  │  0.582 │ 0.901 │ 2025-11-14 14:25│
│ TSLA   │ negative  │ -0.542 │ 0.856 │ 2025-11-14 14:22│
└────────┴───────────┴────────┴───────┴─────────────────┘

🚨 Alertas Ativos
┌────────┬─────────────┬──────────┬───────┬──────┬──────────┐
│ symbol │ signal_type │ strength │ conf  │ time │ exchange │
├────────┼─────────────┼──────────┼───────┼──────┼──────────┤
│ NVDA   │ BUY         │    0.856 │ 0.912 │ 14:30│ alpaca   │
│ AAPL   │ BUY         │    0.743 │ 0.887 │ 14:28│ alpaca   │
└────────┴─────────────┴──────────┴───────┴──────┴──────────┘

📊 Posições Abertas
┌────────┬──────┬────────┬────────┬────────┬─────────┬────────┬──────────┐
│ symbol │ side │  qty   │ entry  │   sl   │   tp    │  open  │ exchange │
├────────┼──────┼────────┼────────┼────────┼─────────┼────────┼──────────┤
│ NVDA   │ BUY  │ 15.000 │ 485.32 │ 475.61 │ 509.59  │  2.3h  │ alpaca   │
│ AAPL   │ BUY  │ 52.000 │ 178.45 │ 174.88 │ 187.37  │  4.1h  │ alpaca   │
│ BTCUSD │ BUY  │  0.125 │ 37250  │ 36133  │ 40230   │  5.8h  │ binance  │
└────────┴──────┴────────┴────────┴────────┴─────────┴────────┴──────────┘

💰 Performance do Portfolio
┌──────────┬──────────┬─────────┬───────────┬────────┬──────────┬─────────┬────────┬─────────────────┐
│ exchange │  value   │  cash   │ positions │ trades │ win_rate │   pnl   │ sharpe │    updated      │
├──────────┼──────────┼─────────┼───────────┼────────┼──────────┼─────────┼────────┼─────────────────┤
│ alpaca   │ 100450.25│ 87235.50│     2     │   12   │   66.7%  │ +450.25 │  1.85  │ 2025-11-14 14:33│
│ binance  │  10125.80│  5487.30│     1     │    8   │   62.5%  │ +125.80 │  1.42  │ 2025-11-14 14:33│
└──────────┴──────────┴─────────┴───────────┴────────┴──────────┴─────────┴────────┴─────────────────┘

===================================
   Resumo
===================================
Notícias coletadas: 195
Alertas ativos: 2
Posições abertas: 3
Trades fechados: 20
P&L Total: +$576.05

📊 Para atualizar: watch -n 30 ./scripts/monitor.sh
📝 Ver logs: tail -f logs/pipeline_20251114.log
```

---

## Cenário 9: Ajustar Estratégia

```python
# Editar engines/realtime_alert_manager.py (linha ~40)

DEFAULT_CONFIG = {
    'watchlist': [
        # Adicionar seus símbolos preferidos
        'AAPL', 'GOOGL', 'MSFT', 'NVDA', 'TSLA',
        'BTCUSDT', 'ETHUSDT', 'SOLUSDT'
    ],
    'thresholds': {
        'min_sentiment_score': 0.2,    # Aumentar para ser mais seletivo
        'min_confidence': 0.8,         # Aumentar para maior certeza
        'lookback_hours': 4,           # Janela de análise
        'signal_expiry_hours': 2       # Validade do sinal
    },
    ...
}

# Editar config/paper_trading.json (risk settings)

{
    "alpaca": {
        "risk_settings": {
            "max_position_size_pct": 10.0,      # % máximo por posição
            "max_portfolio_risk_pct": 20.0,     # % máximo do portfolio em risco
            "default_stop_loss_pct": 2.0,       # Stop-loss padrão
            "default_take_profit_pct": 5.0,     # Take-profit padrão
            "min_confidence": 0.8,              # Confiança mínima
            "kelly_fraction": 0.25              # Fração do Kelly Criterion
        }
    }
}
```

---

## Cenário 10: Troubleshooting

### Problema: Nenhuma notícia coletada

```bash
# Testar RSS
python -c "
from engines.rss import RSSEngine
rss = RSSEngine()
feeds = rss.fetch_all_feeds()
print(f'RSS: {len(feeds)} entries')
for entry in feeds[:3]:
    print(f'  - {entry[\"title\"][:50]}...')
"

# Testar Alpaca
python -c "
from engines.connector import ConnectorEngine
conn = ConnectorEngine()
news = conn.get_alpaca_news(symbols=['AAPL', 'GOOGL'], limit=5)
print(f'Alpaca: {len(news)} news')
print(news[['headline', 'created_at']].head())
"
```

### Problema: FinBERT não analisa

```bash
# Testar modelo
python -c "
from engines.finbert import FinBERTEngine
fb = FinBERTEngine()
result = fb.analyze_text('Tesla stock surges on record deliveries')
print(f'Sentiment: {result[\"sentiment\"]}')
print(f'Score: {result[\"sentiment_score\"]:.3f}')
print(f'Confidence: {result[\"confidence\"]:.3f}')
"
```

### Problema: Trades não executam

```bash
# Verificar credenciais Alpaca
python -c "
from alpaca.trading.client import TradingClient
import json

with open('config/paper_trading.json') as f:
    config = json.load(f)

client = TradingClient(
    config['alpaca']['api_key'],
    config['alpaca']['api_secret'],
    paper=True
)
account = client.get_account()
print(f'Account Status: {account.status}')
print(f'Buying Power: \${float(account.buying_power):,.2f}')
print(f'Cash: \${float(account.cash):,.2f}')
"

# Verificar credenciais Binance
python -c "
import ccxt
import json

with open('config/paper_trading.json') as f:
    config = json.load(f)

exchange = ccxt.binance({
    'apiKey': config['binance']['api_key'],
    'secret': config['binance']['api_secret']
})
exchange.set_sandbox_mode(True)
balance = exchange.fetch_balance()
print(f'USDT Balance: {balance[\"USDT\"][\"free\"]:.2f}')
"
```

### Problema: Database travado

```bash
# Fechar conexões
pkill -f duckdb

# Checkpoint
duckdb data/market_data.duckdb -c "CHECKPOINT"

# Se persistir, backup e recriar
cp data/market_data.duckdb data/market_data.duckdb.backup
rm data/market_data.duckdb
./scripts/setup_pipeline.sh
```

---

## Queries SQL Úteis

```sql
-- Top símbolos por volume de notícias
SELECT 
    symbol,
    COUNT(*) as news_count,
    AVG(sentiment_score) as avg_sentiment,
    AVG(confidence) as avg_confidence
FROM news_by_symbol
WHERE analyzed_at > datetime('now', '-24 hours')
GROUP BY symbol
ORDER BY news_count DESC
LIMIT 20;

-- Performance por símbolo
SELECT 
    symbol,
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(SUM(pnl), 2) as total_pnl,
    ROUND(AVG(holding_period_hours), 1) as avg_duration
FROM paper_trades
WHERE status = 'closed'
GROUP BY symbol
ORDER BY total_pnl DESC;

-- Trades por horário (encontrar melhores horas)
SELECT 
    strftime('%H', opened_at) as hour,
    COUNT(*) as trades,
    ROUND(AVG(pnl), 2) as avg_pnl,
    ROUND(SUM(pnl), 2) as total_pnl
FROM paper_trades
WHERE status = 'closed'
GROUP BY hour
ORDER BY total_pnl DESC;

-- Efetividade dos sinais
SELECT 
    signal_strength_bucket,
    COUNT(*) as alerts,
    COUNT(pt.id) as executed,
    ROUND(AVG(pt.pnl), 2) as avg_pnl
FROM (
    SELECT 
        id,
        symbol,
        CASE 
            WHEN signal_strength >= 0.8 THEN '0.8+'
            WHEN signal_strength >= 0.6 THEN '0.6-0.8'
            ELSE '<0.6'
        END as signal_strength_bucket
    FROM realtime_alerts
) ra
LEFT JOIN paper_trades pt ON ra.id = pt.alert_id
GROUP BY signal_strength_bucket
ORDER BY signal_strength_bucket DESC;
```

---

## Automação com Cron

```bash
# Editar crontab
crontab -e

# Executar pipeline às 9:30 (antes do mercado abrir)
30 9 * * 1-5 cd ~/Documents/GitHub/wawabt && source venv/bin/activate && python engines/pipeline_scheduler.py &

# Backup diário às 2am
0 2 * * * cp ~/Documents/GitHub/wawabt/data/market_data.duckdb ~/backups/market_data_$(date +\%Y\%m\%d).duckdb

# Status report diário às 18h
0 18 * * * cd ~/Documents/GitHub/wawabt && source venv/bin/activate && ./scripts/status.py >> ~/logs/daily_status.txt
```

---

## Next Steps

1. ✅ Configurar API keys
2. ✅ Executar `setup_pipeline.sh`
3. ✅ Testar com `test_pipeline.sh`
4. ✅ Rodar `--test` mode
5. ✅ Monitorar com `status.py`
6. ✅ Ajustar estratégia conforme resultados
7. ✅ Executar em produção (24/7)

📚 **Ver documentação completa:** `docs/USAGE_GUIDE.md`
