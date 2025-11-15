# Guia de Uso - Pipeline Automática de Trading com Sentiment Analysis

## 📋 Índice
1. [Instalação](#instalação)
2. [Configuração](#configuração)
3. [Estrutura de Dados](#estrutura-de-dados)
4. [Executando Componentes](#executando-componentes)
5. [Scheduler Automático](#scheduler-automático)
6. [Monitoramento](#monitoramento)
7. [Troubleshooting](#troubleshooting)

---

## 🔧 Instalação

### 1. Ativar Ambiente Virtual
```bash
cd /Users/wagnermontes/Documents/GitHub/wawabt
source venv/bin/activate
```

### 2. Instalar Dependências
```bash
# Dependências core já instaladas (verificar)
pip install -r requirements.txt

# Instalar APScheduler para o scheduler
pip install apscheduler

# Verificar instalações críticas
python -c "import alpaca; import ccxt; import feedparser; print('✓ Dependências OK')"
```

### 3. Instalar Modelo FinBERT (Primeira Execução)
```python
# Executar uma vez para baixar o modelo
python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
AutoTokenizer.from_pretrained('ProsusAI/finbert'); \
AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

---

## ⚙️ Configuração

### 1. Credenciais de API

Editar `config/paper_trading.json`:

```json
{
    "alpaca": {
        "enabled": true,
        "api_key": "SUA_CHAVE_AQUI",
        "api_secret": "SEU_SECRET_AQUI",
        "base_url": "https://paper-api.alpaca.markets",
        ...
    },
    "binance": {
        "enabled": true,
        "api_key": "SUA_CHAVE_TESTNET_AQUI",
        "api_secret": "SEU_SECRET_TESTNET_AQUI",
        "base_url": "https://testnet.binance.vision",
        ...
    }
}
```

#### Obter Credenciais:

**Alpaca (Paper Trading - GRÁTIS)**
1. Acessar https://alpaca.markets/
2. Criar conta gratuita
3. Ir em "Paper Trading"
4. Gerar API Key e Secret
5. Copiar para `config/paper_trading.json`

**Binance Testnet (GRÁTIS)**
1. Acessar https://testnet.binance.vision/
2. Fazer login com GitHub
3. Gerar API Key e Secret
4. Copiar para `config/paper_trading.json`

### 2. Watchlist de Símbolos

Editar `engines/realtime_alert_manager.py` (linha ~40):

```python
DEFAULT_CONFIG = {
    'watchlist': [
        # US Stocks
        'AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'META', 'AMZN',
        
        # Crypto (formato Binance)
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT'
    ],
    ...
}
```

### 3. Fontes RSS

Verificar/editar `config/rss_sources.json` para adicionar feeds customizados.

---

## 🗄️ Estrutura de Dados

### Schema DuckDB

O sistema usa `data/market_data.duckdb`. Tabelas criadas automaticamente:

```sql
-- Notícias brutas
CREATE TABLE IF NOT EXISTS news_raw (
    id VARCHAR PRIMARY KEY,
    title VARCHAR,
    content TEXT,
    source VARCHAR,
    url VARCHAR,
    published_at TIMESTAMP,
    tickers_mentioned VARCHAR[],
    cryptos_mentioned VARCHAR[],
    content_hash VARCHAR UNIQUE,
    status VARCHAR  -- 'pending', 'processed'
);

-- Sentiment geral
CREATE TABLE IF NOT EXISTS news_sentiment (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR REFERENCES news_raw(id),
    sentiment VARCHAR,  -- 'positive', 'negative', 'neutral'
    sentiment_score DOUBLE,  -- -1.0 a +1.0
    confidence DOUBLE,
    analyzed_at TIMESTAMP
);

-- Sentiment por símbolo
CREATE TABLE IF NOT EXISTS news_by_symbol (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR REFERENCES news_raw(id),
    symbol VARCHAR,
    sentiment VARCHAR,
    sentiment_score DOUBLE,
    confidence DOUBLE,
    analyzed_at TIMESTAMP
);

-- Alertas de trading
CREATE TABLE IF NOT EXISTS realtime_alerts (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    signal_type VARCHAR,  -- 'BUY', 'SELL'
    signal_strength DOUBLE,
    sentiment_score DOUBLE,
    confidence DOUBLE,
    news_count INTEGER,
    generated_at TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR,  -- 'active', 'executed', 'expired'
    exchange VARCHAR  -- 'alpaca', 'binance'
);

-- Trades em papel
CREATE TABLE IF NOT EXISTS paper_trades (
    id VARCHAR PRIMARY KEY,
    alert_id VARCHAR REFERENCES realtime_alerts(id),
    symbol VARCHAR,
    exchange VARCHAR,
    side VARCHAR,  -- 'BUY', 'SELL'
    quantity DOUBLE,
    entry_price DOUBLE,
    stop_loss DOUBLE,
    take_profit DOUBLE,
    status VARCHAR,  -- 'open', 'closed'
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    exit_price DOUBLE,
    pnl DOUBLE,
    pnl_pct DOUBLE,
    exit_reason VARCHAR
);

-- Estado do portfolio
CREATE TABLE IF NOT EXISTS portfolio_state (
    exchange VARCHAR PRIMARY KEY,
    total_value DOUBLE,
    cash DOUBLE,
    positions_value DOUBLE,
    open_positions INTEGER,
    total_trades INTEGER,
    win_rate DOUBLE,
    total_pnl DOUBLE,
    sharpe_ratio DOUBLE,
    updated_at TIMESTAMP
);
```

### Inicializar Database

```bash
# Conectar ao DuckDB
duckdb data/market_data.duckdb

# Copiar e executar o schema acima
# Ou criar arquivo SQL:
cat > init_schema.sql << 'EOF'
-- Cole o schema acima aqui
EOF

duckdb data/market_data.duckdb < init_schema.sql
```

---

## 🚀 Executando Componentes

### Modo Teste Individual

#### 1. NewsCollectorPipeline
```bash
# Coletar notícias de RSS + Alpaca API
python engines/news_collector_pipeline.py

# Verificar resultados
duckdb data/market_data.duckdb -c "SELECT COUNT(*), status FROM news_raw GROUP BY status"
```

#### 2. SentimentAnalysisPipeline
```bash
# Analisar notícias pendentes com FinBERT
python engines/sentiment_pipeline.py

# Verificar sentimentos
duckdb data/market_data.duckdb -c "
SELECT 
    sentiment, 
    COUNT(*) as count,
    AVG(confidence) as avg_conf,
    AVG(sentiment_score) as avg_score
FROM news_sentiment
GROUP BY sentiment
"
```

#### 3. RealtimeAlertManager
```bash
# Gerar sinais de trading
python engines/realtime_alert_manager.py

# Verificar alertas
duckdb data/market_data.duckdb -c "
SELECT 
    symbol, 
    signal_type, 
    signal_strength, 
    confidence,
    generated_at
FROM realtime_alerts
WHERE status = 'active'
ORDER BY signal_strength DESC
LIMIT 10
"
```

#### 4. SignalExecutionManager
```bash
# ATENÇÃO: Vai executar trades reais (paper trading)
# Verificar credenciais antes!
python engines/signal_execution.py

# Verificar trades abertos
duckdb data/market_data.duckdb -c "
SELECT 
    symbol, 
    side, 
    quantity, 
    entry_price, 
    stop_loss,
    take_profit,
    opened_at
FROM paper_trades
WHERE status = 'open'
"
```

#### 5. PerformanceTracker
```bash
# Monitorar P&L dos trades
python engines/performance_tracker.py

# Verificar portfolio
duckdb data/market_data.duckdb -c "
SELECT 
    exchange,
    total_value,
    cash,
    open_positions,
    win_rate,
    total_pnl,
    sharpe_ratio
FROM portfolio_state
"
```

---

## ⏰ Scheduler Automático

### Modo Teste (Execução Única)

```bash
# Executar todos os pipelines uma vez
python engines/pipeline_scheduler.py --test

# Ver logs
tail -f logs/pipeline_$(date +%Y%m%d).log
```

### Modo Produção (Automático)

```bash
# Executar 24/7 com todos os pipelines
python engines/pipeline_scheduler.py

# Ou desabilitar componentes específicos
python engines/pipeline_scheduler.py --disable-execution  # Só monitorar, não executar

# Ver próximas execuções (press Ctrl+C após ver)
python engines/pipeline_scheduler.py
```

### Horários de Execução

| Pipeline | Frequência | Horário |
|----------|-----------|---------|
| NewsCollector | 15 minutos | Sempre |
| SentimentAnalysis | 10 minutos | Sempre |
| AlertManager | 5 minutos | 14:30-21:00 UTC (Market Hours) |
| AlertManager | 30 minutos | Fora do horário (crypto) |
| SignalExecution | 2 minutos | Sempre |
| PerformanceTracker | 15 minutos | Sempre |

### Executar em Background

```bash
# Com nohup
nohup python engines/pipeline_scheduler.py > scheduler.out 2>&1 &

# Ou com screen
screen -S trading_pipeline
python engines/pipeline_scheduler.py
# Ctrl+A, D para detach

# Reattach
screen -r trading_pipeline
```

### Parar Pipeline

```bash
# Ctrl+C (graceful shutdown)
# Ou:
pkill -f pipeline_scheduler.py
```

---

## 📊 Monitoramento

### Logs

```bash
# Tail logs em tempo real
tail -f logs/pipeline_$(date +%Y%m%d).log

# Erros apenas
grep ERROR logs/pipeline_$(date +%Y%m%d).log

# Ver últimas execuções
grep "Pipeline completed" logs/pipeline_$(date +%Y%m%d).log | tail -20
```

### Dashboard SQL (DuckDB)

```bash
# Criar script de monitoramento
cat > monitor.sql << 'EOF'
.mode box
.timer on

-- Status das Notícias
SELECT 'NEWS STATUS' as metric;
SELECT status, COUNT(*) as count 
FROM news_raw 
GROUP BY status;

-- Sentimentos Recentes
SELECT 'RECENT SENTIMENTS' as metric;
SELECT 
    symbol,
    sentiment,
    ROUND(sentiment_score, 2) as score,
    ROUND(confidence, 2) as conf,
    analyzed_at
FROM news_by_symbol
ORDER BY analyzed_at DESC
LIMIT 10;

-- Alertas Ativos
SELECT 'ACTIVE ALERTS' as metric;
SELECT 
    symbol,
    signal_type,
    ROUND(signal_strength, 2) as strength,
    ROUND(confidence, 2) as conf,
    generated_at
FROM realtime_alerts
WHERE status = 'active'
ORDER BY signal_strength DESC
LIMIT 10;

-- Trades Abertos
SELECT 'OPEN POSITIONS' as metric;
SELECT 
    symbol,
    side,
    quantity,
    ROUND(entry_price, 2) as entry,
    ROUND((julianday('now') - julianday(opened_at)) * 24, 1) as hours_open
FROM paper_trades
WHERE status = 'open';

-- Performance
SELECT 'PORTFOLIO PERFORMANCE' as metric;
SELECT 
    exchange,
    ROUND(total_value, 2) as value,
    open_positions,
    total_trades,
    ROUND(win_rate * 100, 1) || '%' as win_rate,
    ROUND(total_pnl, 2) as pnl,
    ROUND(sharpe_ratio, 2) as sharpe
FROM portfolio_state;
EOF

# Executar dashboard
duckdb data/market_data.duckdb < monitor.sql

# Ou criar watch (atualizar a cada 30s)
watch -n 30 'duckdb data/market_data.duckdb < monitor.sql'
```

### Métricas Python

```python
# Criar monitor.py
from engines.smart_db import SmartDatabaseManager

db = SmartDatabaseManager()

# Status geral
status = db.conn.execute("""
    SELECT 
        (SELECT COUNT(*) FROM news_raw WHERE status='pending') as pending_news,
        (SELECT COUNT(*) FROM realtime_alerts WHERE status='active') as active_alerts,
        (SELECT COUNT(*) FROM paper_trades WHERE status='open') as open_trades,
        (SELECT SUM(total_pnl) FROM portfolio_state) as total_pnl
""").fetchdf()

print(status)
```

---

## 🔧 Troubleshooting

### Problema: Notícias não sendo coletadas

```bash
# Verificar feeds RSS
python -c "
from engines.rss import RSSEngine
rss = RSSEngine()
feeds = rss.fetch_all_feeds()
print(f'Collected {len(feeds)} entries')
"

# Verificar Alpaca API
python -c "
from engines.connector import ConnectorEngine
conn = ConnectorEngine()
news = conn.get_alpaca_news(symbols=['AAPL'], limit=10)
print(news.head())
"
```

### Problema: FinBERT não funcionando

```bash
# Verificar modelo
python -c "
from engines.finbert import FinBERTEngine
fb = FinBERTEngine()
result = fb.analyze_text('Apple stock surges on strong earnings')
print(result)
"

# Reinstalar transformers
pip install --upgrade transformers torch
```

### Problema: Trades não sendo executados

```bash
# Verificar credenciais Alpaca
python -c "
from alpaca.trading.client import TradingClient
client = TradingClient('API_KEY', 'API_SECRET', paper=True)
account = client.get_account()
print(f'Cash: {account.cash}, Buying Power: {account.buying_power}')
"

# Verificar credenciais Binance
python -c "
import ccxt
exchange = ccxt.binance({'apiKey': 'KEY', 'secret': 'SECRET'})
exchange.set_sandbox_mode(True)
balance = exchange.fetch_balance()
print(balance['USDT'])
"
```

### Problema: Scheduler não iniciando

```bash
# Verificar APScheduler
pip install apscheduler

# Testar modo teste
python engines/pipeline_scheduler.py --test

# Verificar logs
tail -f logs/pipeline_$(date +%Y%m%d).log
```

### Problema: Database locked

```bash
# Fechar todas as conexões
pkill -f duckdb

# Backup e recriar
cp data/market_data.duckdb data/market_data.duckdb.bak
duckdb data/market_data.duckdb -c "CHECKPOINT"
```

### Reset Completo

```bash
# CUIDADO: Apaga todos os dados!
rm data/market_data.duckdb
rm -rf logs/*
rm -rf data/market/*
rm -rf data/news/*

# Reinicializar schema
duckdb data/market_data.duckdb < init_schema.sql

# Testar pipelines
python engines/pipeline_scheduler.py --test
```

---

## 📈 Próximos Passos

1. **Primeira Execução**: Rodar `--test` e verificar cada pipeline
2. **Ajustar Configurações**: Editar watchlist, risk settings em `config/paper_trading.json`
3. **Modo Produção**: Executar scheduler em background com `nohup` ou `screen`
4. **Monitorar Resultados**: Usar dashboard SQL para acompanhar performance
5. **Otimizar Estratégia**: Ajustar thresholds em `realtime_alert_manager.py` baseado em resultados

---

## 📚 Referências

- **Backtrader Docs**: https://www.backtrader.com/docu/
- **Alpaca API**: https://alpaca.markets/docs/
- **CCXT Docs**: https://docs.ccxt.com/
- **FinBERT**: https://huggingface.co/ProsusAI/finbert
- **APScheduler**: https://apscheduler.readthedocs.io/

---

## ⚠️ Avisos Importantes

1. **Paper Trading Only**: Este sistema usa apenas contas de simulação (Alpaca Paper e Binance Testnet)
2. **Não é Conselho Financeiro**: Use por sua conta e risco
3. **Monitorar Sempre**: Mesmo em paper trading, monitore os resultados
4. **Rate Limits**: Respeite os limites de API das exchanges
5. **Backup Regular**: Faça backup do database periodicamente

```bash
# Backup automático diário
crontab -e
# Adicionar:
0 2 * * * cp ~/Documents/GitHub/wawabt/data/market_data.duckdb ~/backups/market_data_$(date +\%Y\%m\%d).duckdb
```
