# 📋 PLANO: PIPELINE AUTOMATIZADA DE SENTIMENTO DE NOTÍCIAS

## 🎯 Objetivo
Criar uma pipeline totalmente automatizada que:
1. Coleta notícias de todas as fontes (APIs + RSS)
2. Processa com FinBERT para análise de sentimento
3. Salva dados estruturados acessíveis para traders e estratégias
4. **Executa trades automaticamente em paper trading (Alpaca + Binance Testnet)**
5. Roda continuamente com monitoramento e tracking de performance

---

## 🏗️ ARQUITETURA DA PIPELINE

```
┌─────────────────────────────────────────────────────────────┐
│                     STAGE 1: COLLECTION                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   RSS    │  │  Yahoo   │  │ Benzinga │  │ CoinDesk │   │
│  │  Feeds   │  │ Finance  │  │   API    │  │   API    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │              │          │
│       └─────────────┴──────────────┴──────────────┘          │
│                           ▼                                   │
│                  NewsCollectorPipeline                        │
│           (dedup, normalize, extract symbols)                 │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 2: SENTIMENT ANALYSIS                 │
│                                                               │
│                    FinBERT Engine                            │
│         (batch processing, confidence scoring)               │
│                                                               │
│  Input: Raw news (title + description)                      │
│  Output: sentiment, confidence, scores                       │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 3: ENRICHMENT                       │
│                                                               │
│               SymbolReferenceEngine                          │
│         (extract mentioned symbols, validate)                │
│                                                               │
│               MarketDataEnricher                             │
│      (fetch current prices, calculate impact)                │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   STAGE 4: STORAGE                           │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   DuckDB    │  │   Parquet   │  │    JSON     │         │
│  │ (queryable) │  │  (archival) │  │  (realtime) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                               │
│  Tables:                                                      │
│  - news_raw (todas as notícias)                             │
│  - news_sentiment (com análise)                             │
│  - news_by_symbol (agregado por símbolo)                    │
│  - realtime_alerts (sinais para trader)                     │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 STAGE 5: SIGNAL EXECUTION                    │
│                                                               │
│              SignalExecutionManager                          │
│        (converte alertas em ordens de trading)               │
│                                                               │
│  ┌─────────────────┐        ┌─────────────────┐            │
│  │ PaperTradeAlpaca│        │PaperTradeBinance│            │
│  │  (US Stocks)    │        │  (Crypto Testnet)│           │
│  └─────────────────┘        └─────────────────┘            │
│                                                               │
│  - Validação de sinais (confidence, volume)                 │
│  - Position sizing (Kelly criterion, fixed %)               │
│  - Risk management (stop-loss, take-profit)                 │
│  - Order execution (market, limit)                          │
│  - Performance tracking (PnL, Sharpe, Win Rate)             │
└───────────────────────────┬───────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   STAGE 6: DELIVERY                          │
│                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Strategy   │  │   Trader    │  │   Monitor   │         │
│  │   Access    │  │  Dashboard  │  │   Alerts    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                               │
│  - SQL queries via DuckDB                                    │
│  - Parquet files para pandas                                 │
│  - JSON para web/mobile                                      │
│  - Webhooks para alertas                                     │
│  - Live trade feed (WebSocket)                              │
│  - Performance dashboard (PnL, positions)                   │
└───────────────────────────────────────────────────────────────┘
```

---

## 📦 COMPONENTES A CRIAR

### 1. **NewsCollectorPipeline** (`engines/news_collector_pipeline.py`)
```python
class NewsCollectorPipeline:
    """Pipeline de coleta de notícias de múltiplas fontes"""
    
    - collect_rss_feeds()          # Todas as fontes RSS
    - collect_yahoo_api()           # Yahoo Finance API
    - collect_benzinga_api()        # Benzinga API (se disponível)
    - collect_coindesk_api()        # CoinDesk API
    - deduplicate()                 # Remove duplicatas por hash
    - normalize_format()            # Padroniza estrutura
    - extract_symbols()             # Extrai símbolos mencionados
    - save_raw()                    # Salva em news_raw
```

### 2. **SentimentAnalysisPipeline** (`engines/sentiment_pipeline.py`)
```python
class SentimentAnalysisPipeline:
    """Pipeline de análise de sentimento"""
    
    - load_unprocessed_news()       # Carrega news sem sentiment
    - batch_analyze()               # Processa em lotes (eficiência)
    - calculate_confidence()        # Calcula confidence scores
    - per_symbol_analysis()         # Sentimento por símbolo
    - save_sentiment()              # Salva em news_sentiment
```

### 3. **MarketEnrichmentPipeline** (`engines/market_enrichment_pipeline.py`)
```python
class MarketEnrichmentPipeline:
    """Enriquece notícias com dados de mercado"""
    
    - fetch_current_prices()        # Preços atuais dos símbolos
    - calculate_pre_news_prices()   # Preços antes da notícia
    - track_post_news_impact()      # Mudanças após notícia (1h, 4h, 24h)
    - calculate_correlations()      # Correlações sentimento-preço
    - save_enriched()               # Salva dados enriquecidos
```

### 4. **RealtimeAlertManager** (`engines/realtime_alerts.py`)
```python
class RealtimeAlertManager:
    """Gerencia alertas em tempo real para traders"""
    
    - check_sentiment_threshold()   # Sentimento extremo detectado
    - check_volume_spike()          # Spike de notícias
    - check_confidence_high()       # Alta confiança em sentimento
    - generate_trading_signal()     # Gera sinal baseado em regras
    - send_notification()           # Webhook/email/Telegram
    - save_to_realtime_table()      # Tabela de alertas
```

### 5. **SignalExecutionManager** (`engines/signal_execution.py`)
```python
class SignalExecutionManager:
    """Gerencia execução de sinais de trading"""
    
    - load_active_signals()         # Carrega sinais de realtime_alerts
    - validate_signal()             # Valida confidence, volume, timing
    - calculate_position_size()     # Kelly criterion ou fixed %
    - set_risk_parameters()         # Stop-loss, take-profit
    - route_order()                 # Roteia para Alpaca ou Binance
    - track_execution()             # Salva em paper_trades
    - update_portfolio()            # Atualiza posições
```

### 6. **PaperTradeAlpaca** (`engines/paper_trade_alpaca.py`)
```python
class PaperTradeAlpaca:
    """Executor de paper trading para Alpaca (US Stocks)"""
    
    - connect()                     # Conecta API paper trading
    - get_account()                 # Status da conta
    - get_positions()               # Posições abertas
    - place_order()                 # Market/limit order
    - cancel_order()                # Cancela ordem
    - get_order_status()            # Status da ordem
    - get_bars()                    # Historical prices
    - stream_trades()               # WebSocket real-time
```

### 7. **PaperTradeBinance** (`engines/paper_trade_binance.py`)
```python
class PaperTradeBinance:
    """Executor de paper trading para Binance (Crypto Testnet)"""
    
    - connect()                     # Conecta Binance Testnet
    - get_account()                 # Balances testnet
    - get_positions()               # Posições abertas
    - place_order()                 # Market/limit order
    - cancel_order()                # Cancela ordem
    - get_order_status()            # Status da ordem
    - get_klines()                  # Historical candles
    - stream_ticker()               # WebSocket real-time
```

### 8. **PipelineOrchestrator** (`scripts/pipeline_orchestrator.py`)
```python
class PipelineOrchestrator:
    """Orquestra toda a pipeline"""
    
    - run_collection_cycle()        # Ciclo de coleta
    - run_sentiment_cycle()         # Ciclo de análise
    - run_enrichment_cycle()        # Ciclo de enriquecimento
    - run_alert_cycle()             # Ciclo de alertas
    - run_execution_cycle()         # Ciclo de execução de trades
    - run_performance_cycle()       # Calcula métricas de performance
    - monitor_health()              # Monitora saúde da pipeline
    - log_metrics()                 # Logs e métricas
```

### 9. **TraderDashboardAPI** (`engines/trader_api.py`)
```python
class TraderDashboardAPI:
    """API para acesso dos traders aos dados"""
    
    - get_latest_news(symbol)       # Últimas notícias de símbolo
    - get_sentiment_summary(symbol) # Resumo de sentimento
    - get_realtime_alerts()         # Alertas ativos
    - get_sentiment_history()       # Histórico de sentimento
    - get_open_positions()          # Posições abertas (paper trading)
    - get_trade_history()           # Histórico de trades
    - get_performance_metrics()     # PnL, Sharpe, Win Rate
    - query_custom(sql)             # Query SQL customizada
```

---

## 🗄️ ESTRUTURA DE DADOS

### Tabela: `news_raw`
```sql
CREATE TABLE news_raw (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    source VARCHAR,
    category VARCHAR,
    title TEXT,
    description TEXT,
    link VARCHAR,
    author VARCHAR,
    content_hash VARCHAR UNIQUE,
    symbols_mentioned VARCHAR[],  -- Array de símbolos
    collected_at TIMESTAMP,
    processing_status VARCHAR      -- 'pending', 'processed', 'error'
);
```

### Tabela: `news_sentiment`
```sql
CREATE TABLE news_sentiment (
    news_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    source VARCHAR,
    title TEXT,
    link VARCHAR,
    sentiment VARCHAR,              -- 'positive', 'negative', 'neutral'
    confidence FLOAT,
    positive_score FLOAT,
    negative_score FLOAT,
    neutral_score FLOAT,
    analyzed_at TIMESTAMP,
    model_version VARCHAR
);
```

### Tabela: `news_by_symbol`
```sql
CREATE TABLE news_by_symbol (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    news_id VARCHAR,
    timestamp TIMESTAMP,
    sentiment VARCHAR,
    confidence FLOAT,
    sentiment_score FLOAT,          -- Composite score (-1 to 1)
    is_symbol_specific BOOLEAN,     -- Notícia específica do símbolo?
    matched_sentence TEXT,          -- Sentença que menciona símbolo
    INDEX (symbol, timestamp)
);
```

### Tabela: `realtime_alerts`
```sql
CREATE TABLE realtime_alerts (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    alert_type VARCHAR,             -- 'sentiment_extreme', 'volume_spike', etc
    severity VARCHAR,               -- 'low', 'medium', 'high'
    sentiment_score FLOAT,
    confidence FLOAT,
    news_count INT,
    signal VARCHAR,                 -- 'buy', 'sell', 'watch'
    message TEXT,
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR,                 -- 'active', 'expired', 'executed', 'rejected'
    executed_trade_id VARCHAR,      -- FK para paper_trades
    INDEX (symbol, status, created_at)
);
```

### Tabela: `paper_trades`
```sql
CREATE TABLE paper_trades (
    id VARCHAR PRIMARY KEY,
    alert_id VARCHAR,               -- FK para realtime_alerts
    exchange VARCHAR,               -- 'alpaca', 'binance'
    symbol VARCHAR,
    side VARCHAR,                   -- 'buy', 'sell'
    order_type VARCHAR,             -- 'market', 'limit'
    quantity FLOAT,
    entry_price FLOAT,
    exit_price FLOAT,
    stop_loss FLOAT,
    take_profit FLOAT,
    status VARCHAR,                 -- 'pending', 'filled', 'closed', 'cancelled'
    sentiment_score FLOAT,
    confidence FLOAT,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    pnl FLOAT,                      -- Profit/Loss em $
    pnl_pct FLOAT,                  -- Profit/Loss em %
    holding_period INT,             -- Minutos
    commission FLOAT,
    notes TEXT,
    INDEX (symbol, entry_time),
    INDEX (status, exchange)
);
```

### Tabela: `portfolio_state`
```sql
CREATE TABLE portfolio_state (
    timestamp TIMESTAMP PRIMARY KEY,
    exchange VARCHAR,
    total_value FLOAT,
    cash_balance FLOAT,
    equity_value FLOAT,
    open_positions INT,
    total_pnl FLOAT,
    daily_pnl FLOAT,
    sharpe_ratio FLOAT,
    win_rate FLOAT,
    avg_win FLOAT,
    avg_loss FLOAT,
    max_drawdown FLOAT,
    INDEX (exchange, timestamp)
);
```

### Tabela: `market_impact`
```sql
CREATE TABLE market_impact (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    news_id VARCHAR,
    news_timestamp TIMESTAMP,
    sentiment_score FLOAT,
    pre_news_price FLOAT,
    change_1h FLOAT,
    change_4h FLOAT,
    change_24h FLOAT,
    change_48h FLOAT,
    change_168h FLOAT,
    correlation_score FLOAT,
    INDEX (symbol, news_timestamp)
);
```

---

## ⏱️ SCHEDULE DE EXECUÇÃO

### Coleta de Notícias
```
* Cada 15 minutos: RSS feeds (rápidas, atualizações frequentes)
* Cada 1 hora: APIs (limite de rate, mais custosas)
* Horário de mercado: Cada 5 minutos (pico de atividade)
```

### Análise de Sentimento
```
* Cada 10 minutos: Batch processing de notícias pending
* Prioridade: Notícias de símbolos em watchlist
* GPU scheduling: Lotes de 50-100 notícias
```

### Enriquecimento de Mercado
```
* Cada 1 hora: Fetch de preços e cálculo de impacto
* Cada 4 horas: Recalcular correlações
* Final do dia: Análise completa do dia
```

### Alertas em Tempo Real
```
* Cada 5 minutos durante mercado aberto
* Cada 30 minutos fora de horário
* Trigger imediato: Sentimento extremo detectado
```

### Execução de Trades
```
* Cada 2 minutos: Processa sinais ativos (status='active')
* Alpaca: 09:30-16:00 EST (mercado US)
* Binance: 24/7 (crypto testnet)
* Risk check antes de cada ordem
```

### Performance Tracking
```
* Cada 15 minutos: Atualiza portfolio_state
* Cada 1 hora: Calcula métricas (Sharpe, drawdown)
* Final do dia: Relatório diário de performance
```

---

## 🔄 FLUXO DE DADOS

```
1. NewsCollectorPipeline.run()
   ├─> Coleta de todas as fontes
   ├─> Deduplicação por content_hash
   ├─> Extração de símbolos mencionados
   └─> Save em news_raw (status='pending')

2. SentimentAnalysisPipeline.run()
   ├─> Load news WHERE status='pending'
   ├─> Batch analyze com FinBERT
   ├─> Calculate sentiment_score composto
   ├─> Per-symbol sentiment analysis
   ├─> Save em news_sentiment
   ├─> Save em news_by_symbol
   └─> Update news_raw (status='processed')

3. MarketEnrichmentPipeline.run()
   ├─> Load processed news
   ├─> Fetch current prices
   ├─> Calculate pre/post news changes
   ├─> Track impact windows (1h, 4h, 24h...)
   └─> Save em market_impact

4. RealtimeAlertManager.run()
   ├─> Check sentiment thresholds
   ├─> Check volume spikes
   ├─> Generate trading signals
   ├─> Send notifications
   └─> Save em realtime_alerts (status='active')

5. SignalExecutionManager.run()
   ├─> Load signals WHERE status='active'
   ├─> Validate signal (confidence, timing, risk)
   ├─> Calculate position size (Kelly criterion)
   ├─> Route to Alpaca or Binance
   ├─> Place order (market/limit)
   ├─> Update realtime_alerts (status='executed')
   └─> Save em paper_trades

6. PaperTradeAlpaca/Binance.execute()
   ├─> Connect to API (paper/testnet)
   ├─> Check account balance
   ├─> Place order
   ├─> Set stop-loss/take-profit
   ├─> Monitor execution
   └─> Return order confirmation

7. PerformanceTracker.run()
   ├─> Load all open positions
   ├─> Update current prices
   ├─> Calculate unrealized PnL
   ├─> Close positions (stop-loss/take-profit hit)
   ├─> Calculate metrics (Sharpe, Win Rate)
   └─> Save em portfolio_state

8. TraderDashboardAPI.serve()
   ├─> Query endpoints
   ├─> Real-time WebSocket (trades feed)
   ├─> Performance dashboard
   └─> JSON/REST responses
```

---

## � CONFIGURAÇÃO DE APIs (Paper Trading)

### Alpaca Paper Trading
```json
// config/alpaca_paper.json
{
    "api_key": "YOUR_ALPACA_PAPER_KEY",
    "api_secret": "YOUR_ALPACA_PAPER_SECRET",
    "base_url": "https://paper-api.alpaca.markets",
    "data_url": "https://data.alpaca.markets",
    "enabled": true,
    "risk_settings": {
        "max_position_size_pct": 10,    // Max 10% do portfolio por posição
        "max_portfolio_risk_pct": 20,    // Max 20% de risco total
        "default_stop_loss_pct": 2.0,    // Stop-loss padrão 2%
        "default_take_profit_pct": 5.0,  // Take-profit padrão 5%
        "min_confidence": 0.8,           // Confiança mínima para trade
        "kelly_fraction": 0.25           // Usar 25% do Kelly criterion
    },
    "trading_hours": {
        "start": "09:30",
        "end": "16:00",
        "timezone": "America/New_York"
    }
}
```

### Binance Testnet (Crypto)
```json
// config/binance_testnet.json
{
    "api_key": "YOUR_BINANCE_TESTNET_KEY",
    "api_secret": "YOUR_BINANCE_TESTNET_SECRET",
    "base_url": "https://testnet.binance.vision",
    "enabled": true,
    "risk_settings": {
        "max_position_size_pct": 15,     // Crypto mais volátil
        "max_portfolio_risk_pct": 25,
        "default_stop_loss_pct": 3.0,    // Stop-loss mais largo
        "default_take_profit_pct": 8.0,
        "min_confidence": 0.85,          // Confiança maior para crypto
        "kelly_fraction": 0.2
    },
    "trading_pairs": [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT",
        "ADAUSDT", "XRPUSDT", "DOGEUSDT", "MATICUSDT"
    ],
    "24_7_trading": true
}
```

### Obter Credenciais

#### Alpaca Paper Trading (FREE)
1. Acesse: https://alpaca.markets/
2. Sign up para conta
3. No dashboard, vá em "Paper Trading"
4. Copie `API Key` e `Secret Key`
5. Paper account começa com $100,000 virtual

#### Binance Testnet (FREE)
1. Acesse: https://testnet.binance.vision/
2. Login com GitHub ou email
3. Gere API Keys no dashboard
4. Testnet já vem com saldo virtual (BTC, ETH, USDT)
5. Reset diário do saldo se necessário

---

## �📊 INTERFACES PARA TRADER

### 1. **SQL Query Interface**
```python
# Trader pode fazer queries diretas
from engines.trader_api import TraderAPI

api = TraderAPI()

# Últimas notícias positivas de AAPL
news = api.query("""
    SELECT * FROM news_by_symbol
    WHERE symbol = 'AAPL'
    AND sentiment = 'positive'
    AND confidence > 0.8
    ORDER BY timestamp DESC
    LIMIT 10
""")
```

### 2. **Python DataFrame Access**
```python
import pandas as pd

# Carregar dados para análise
df = pd.read_parquet('data/analysis/news_by_symbol.parquet')

# Filtrar por símbolo
aapl_news = df[df['symbol'] == 'AAPL']

# Análise de sentimento
sentiment_summary = aapl_news.groupby('sentiment').agg({
    'confidence': 'mean',
    'sentiment_score': 'mean'
})
```

### 3. **Realtime Alert Stream**
```python
# WebSocket para alertas em tempo real
from engines.trader_api import AlertStream

stream = AlertStream()

@stream.on_alert
def handle_alert(alert):
    if alert['severity'] == 'high':
        print(f"⚠️  {alert['symbol']}: {alert['message']}")
        # Execute trade logic
```

### 4. **REST API Endpoints**
```
GET  /api/news/latest?symbol=AAPL&limit=10
GET  /api/sentiment/summary?symbol=AAPL&period=24h
GET  /api/alerts/active
GET  /api/market/impact?symbol=AAPL
GET  /api/trades/open                       # Posições abertas
GET  /api/trades/history?symbol=AAPL       # Histórico de trades
GET  /api/performance/metrics               # PnL, Sharpe, Win Rate
GET  /api/portfolio/state                   # Estado do portfolio
POST /api/query (custom SQL)
POST /api/trades/close?id=123              # Fechar posição manualmente
```

---

## 🛠️ IMPLEMENTAÇÃO FASEADA

### **FASE 1: Core Pipeline** (Semana 1)
- [ ] `NewsCollectorPipeline` com RSS + Yahoo API
- [ ] `SentimentAnalysisPipeline` com FinBERT batch
- [ ] Tabelas DuckDB (news_raw, news_sentiment)
- [ ] Script básico de orquestração

### **FASE 2: Enrichment** (Semana 2)
- [ ] `MarketEnrichmentPipeline` 
- [ ] Tabela `market_impact`
- [ ] Symbol extraction e validation
- [ ] Correlação sentimento-preço

### **FASE 3: Realtime Alerts** (Semana 3)
- [ ] `RealtimeAlertManager`
- [ ] Tabela `realtime_alerts`
- [ ] Signal generation logic (usar estratégia campeã: signal_high_conf)
- [ ] Notification system (email/webhook)

### **FASE 4: Paper Trading Execution** (Semana 4)
- [ ] `SignalExecutionManager`
- [ ] `PaperTradeAlpaca` (US Stocks paper trading)
- [ ] `PaperTradeBinance` (Crypto testnet)
- [ ] Tabelas `paper_trades` + `portfolio_state`
- [ ] Position sizing & risk management
- [ ] Order routing logic

### **FASE 5: Performance Tracking** (Semana 5)
- [ ] `PerformanceTracker`
- [ ] Cálculo de métricas (Sharpe, Win Rate, Max Drawdown)
- [ ] Close positions (stop-loss/take-profit)
- [ ] Daily/weekly reports

### **FASE 6: Trader Interface** (Semana 6)
- [ ] `TraderDashboardAPI`
- [ ] REST API endpoints (news, sentiment, trades, performance)
- [ ] Query interface
- [ ] WebSocket para real-time (trades feed)
- [ ] Performance dashboard

### **FASE 7: Monitoring & Optimization** (Semana 7)
- [ ] Health monitoring (pipeline + trading)
- [ ] Performance metrics (latency, accuracy, PnL)
- [ ] Error handling & retry logic
- [ ] Auto-scaling batch sizes
- [ ] Backtesting validation vs paper trading results

---

## 🚀 DEPLOYMENT

### Opção 1: Cron Jobs (Simples)
```bash
# /etc/crontab
*/15 * * * * cd /path/to/wawabt && venv/bin/python scripts/pipeline_orchestrator.py --stage collection
*/10 * * * * cd /path/to/wawabt && venv/bin/python scripts/pipeline_orchestrator.py --stage sentiment
0 * * * * cd /path/to/wawabt && venv/bin/python scripts/pipeline_orchestrator.py --stage enrichment
*/5 9-16 * * 1-5 cd /path/to/wawabt && venv/bin/python scripts/pipeline_orchestrator.py --stage alerts
```

### Opção 2: Systemd Services (Recomendado)
```ini
# /etc/systemd/system/news-pipeline.service
[Unit]
Description=News Sentiment Pipeline
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/path/to/wawabt
ExecStart=/path/to/wawabt/venv/bin/python scripts/pipeline_orchestrator.py --daemon
Restart=always

[Install]
WantedBy=multi-user.target
```

### Opção 3: Docker Container (Produção)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "scripts/pipeline_orchestrator.py", "--daemon"]
```

---

## 📈 MÉTRICAS & MONITORING

### Métricas a Coletar
- News collection rate (por fonte)
- Sentiment analysis throughput
- Pipeline latency (collection → alert)
- Database size growth
- Error rates
- API rate limit usage

### Dashboards
- Grafana para visualização
- Prometheus para métricas
- Alertmanager para problemas

---

## 🔒 SEGURANÇA & CONFIABILIDADE

### Deduplicação
- Content hash para evitar duplicatas
- Unique constraints no banco
- Check antes de processar

### Error Handling
- Retry logic com backoff exponencial
- Dead letter queue para falhas persistentes
- Logging detalhado

### Rate Limiting
- Respeitar limites de API
- Backoff quando necessário
- Rotação de proxies se disponível

### Data Integrity
- Validação de schema
- Foreign key constraints
- Transações atomicas

---

## 💰 CUSTOS ESTIMADOS

### Recursos Computacionais
- CPU: Moderate (coleta e orquestração)
- GPU: Optional (acelera FinBERT, mas CPU é OK)
- RAM: 8-16GB (batch processing)
- Disk: 50-100GB (crescimento de ~1GB/mês)

### APIs & Trading
- **Alpaca Paper Trading**: FREE (100% gratuito, sem limites)
- **Binance Testnet**: FREE (100% gratuito, saldo virtual)
- Yahoo Finance: FREE
- Benzinga: ~$50-200/mês (opcional)
- CoinDesk: FREE
- RSS Feeds: FREE

### Infraestrutura
- VPS/Cloud: $20-50/mês
- Backup storage: $5-10/mês
- **Total: ~$25-260/mês (paper trading = $0)**

---

## ✅ CRITÉRIOS DE SUCESSO

### Pipeline de Dados
1. **Cobertura**: 80%+ das notícias relevantes coletadas
2. **Latência**: < 15 minutos da publicação ao alerta
3. **Accuracy**: Sentimento correto em 85%+ dos casos
4. **Uptime**: 99%+ de disponibilidade
5. **Usabilidade**: Trader consegue acessar dados em < 30 segundos

### Paper Trading Performance
1. **Sharpe Ratio**: Target > 3.0 (baseline: 5.09 do backtest)
2. **Win Rate**: Target > 15% (baseline: 17.1% do backtest)
3. **Max Drawdown**: < 10%
4. **Order Execution**: 95%+ de ordens executadas com sucesso
5. **Latency**: < 5 minutos do alerta à ordem executada
6. **Validação**: Paper trading deve aproximar resultados do backtest (±20%)

---

## 📚 PRÓXIMOS PASSOS IMEDIATOS

1. ✅ Aprovar este plano
2. 🔨 Criar `NewsCollectorPipeline` (Fase 1)
3. 🔨 Criar `SentimentAnalysisPipeline` (Fase 1)
4. 🔨 Criar `PipelineOrchestrator` (Fase 1)
5. 🧪 Testar pipeline completa com dados reais
6. 🚀 Deploy inicial (cron jobs)
7. 📊 Monitorar e iterar

---

**Quer que eu comece a implementação da FASE 1?**
