# 🤖 Pipeline Automática de Trading com Sentiment Analysis

Sistema completo de trading automatizado usando análise de sentimento de notícias com FinBERT e paper trading em Alpaca (stocks) e Binance (crypto).

## 🚀 Quick Start

```bash
# 1. Ativar ambiente virtual
source venv/bin/activate

# 2. Setup inicial (baixa modelo FinBERT, cria database, testa componentes)
./scripts/setup_pipeline.sh

# 3. Configurar credenciais
# Editar config/paper_trading.json com suas chaves de API:
#   - Alpaca Paper Trading: https://alpaca.markets/
#   - Binance Testnet: https://testnet.binance.vision/

# 4. Testar componentes
./scripts/test_pipeline.sh

# 5. Executar em modo teste (uma vez)
python engines/pipeline_scheduler.py --test

# 6. Ver status
./scripts/status.py
# ou
./scripts/monitor.sh

# 7. Executar em produção (24/7)
python engines/pipeline_scheduler.py
```

## 📊 Como Funciona

```
┌─────────────────────────────────────────────────────────────┐
│                  Pipeline de Trading Automática             │
└─────────────────────────────────────────────────────────────┘

  [RSS Feeds + Alpaca News API]
              ↓
    ┌──────────────────┐
    │ NewsCollector    │ ← Coleta notícias (cada 15min)
    │ Pipeline         │
    └────────┬─────────┘
             ↓
         [news_raw]
             ↓
    ┌──────────────────┐
    │ Sentiment        │ ← FinBERT analysis (cada 10min)
    │ Pipeline         │
    └────────┬─────────┘
             ↓
    [news_sentiment + news_by_symbol]
             ↓
    ┌──────────────────┐
    │ Alert Manager    │ ← Gera sinais (cada 5min em market hours)
    │                  │   Thresholds: score>0.2, conf>0.8
    └────────┬─────────┘
             ↓
      [realtime_alerts]
             ↓
    ┌──────────────────┐
    │ Signal           │ ← Executa trades (cada 2min)
    │ Execution        │   Alpaca (stocks) / Binance (crypto)
    └────────┬─────────┘
             ↓
      [paper_trades]
             ↓
    ┌──────────────────┐
    │ Performance      │ ← Monitora P&L (cada 15min)
    │ Tracker          │   Stop-loss / Take-profit
    └──────────────────┘
```

## 🏗️ Arquitetura

### Componentes Core

- **NewsCollectorPipeline**: Coleta notícias de RSS feeds e Alpaca News API
- **SentimentAnalysisPipeline**: Analisa sentimento usando FinBERT (ProsusAI/finbert)
- **RealtimeAlertManager**: Gera sinais de trading baseado em thresholds
- **SignalExecutionManager**: Executa trades via Alpaca (stocks) ou Binance (crypto)
- **PerformanceTracker**: Monitora posições abertas e calcula P&L
- **PipelineScheduler**: Orquestra tudo com APScheduler

### Backtrader Integration

- **AlpacaStore/Broker/Data**: Integração com Alpaca para US stocks
- **CCXTStore/Broker**: Integração universal com exchanges crypto (via CCXT)

### Engines Reutilizados

- **RSSEngine**: Coleta feeds RSS com suporte a proxy
- **NewsEngine**: Validação e deduplicação de notícias
- **FinBERTEngine**: Análise de sentimento com modelo FinBERT
- **ConnectorEngine**: Múltiplas fontes de dados (Yahoo, Alpaca, Binance, CCXT)
- **SmartDatabaseManager**: DuckDB + Parquet com partitioning inteligente
- **AutoFetchData**: Database-first approach para backtrader feeds

## 📁 Estrutura de Dados

Database: `data/market_data.duckdb`

Tabelas principais:
- `news_raw`: Notícias coletadas (status: pending/processed)
- `news_sentiment`: Análise geral de sentimento
- `news_by_symbol`: Sentimento por símbolo
- `realtime_alerts`: Sinais de trading (status: active/executed/expired)
- `paper_trades`: Trades executados (status: open/closed)
- `portfolio_state`: Estado do portfolio por exchange

## 🎯 Estratégia Champion

Baseada em análise de 77 símbolos e 46,277 sentiments:

```python
# Thresholds
min_sentiment_score = 0.2    # -1.0 a +1.0
min_confidence = 0.8         # 0.0 a 1.0
lookback_hours = 4           # Janela de análise

# Risk Management
stop_loss = 2% (stocks) / 3% (crypto)
take_profit = 5% (stocks) / 8% (crypto)
max_position = 10% (stocks) / 15% (crypto)
kelly_fraction = 0.25 (stocks) / 0.2 (crypto)

# Performance (backtest)
Sharpe Ratio: 5.09
Total Return: 1319%
Win Rate: 17.1%
```

## 🛠️ Scripts Úteis

```bash
# Setup e inicialização
./scripts/setup_pipeline.sh

# Testes
./scripts/test_pipeline.sh

# Monitoramento
./scripts/status.py              # Status rápido
./scripts/monitor.sh             # Dashboard completo
watch -n 30 ./scripts/status.py  # Auto-refresh

# Logs
tail -f logs/pipeline_$(date +%Y%m%d).log

# Database queries
duckdb data/market_data.duckdb -box -c "SELECT * FROM realtime_alerts WHERE status='active'"
```

## 🔐 Configuração de API Keys

### Alpaca (Paper Trading - GRÁTIS)

1. Acesse https://alpaca.markets/
2. Crie conta gratuita
3. Vá em "Paper Trading"
4. Gere API Key e Secret
5. Edite `config/paper_trading.json`:

```json
{
  "alpaca": {
    "api_key": "SUA_CHAVE",
    "api_secret": "SEU_SECRET",
    ...
  }
}
```

### Binance Testnet (GRÁTIS)

1. Acesse https://testnet.binance.vision/
2. Login com GitHub
3. Gere API Key e Secret
4. Edite `config/paper_trading.json`:

```json
{
  "binance": {
    "api_key": "SUA_CHAVE_TESTNET",
    "api_secret": "SEU_SECRET_TESTNET",
    ...
  }
}
```

## 📊 Monitoramento em Tempo Real

### Dashboard Python (Recomendado)

```bash
# Status rápido
./scripts/status.py

# Auto-refresh a cada 30s
watch -n 30 ./scripts/status.py
```

### Dashboard Shell

```bash
# Monitor completo
./scripts/monitor.sh

# Auto-refresh
watch -n 30 ./scripts/monitor.sh
```

### Queries Diretas

```bash
# Alertas ativos
duckdb data/market_data.duckdb -box -c "
SELECT symbol, signal_type, signal_strength, confidence 
FROM realtime_alerts 
WHERE status='active' 
ORDER BY signal_strength DESC"

# Posições abertas
duckdb data/market_data.duckdb -box -c "
SELECT symbol, side, quantity, entry_price, 
       ROUND((julianday('now') - julianday(opened_at)) * 24, 1) as hours_open
FROM paper_trades 
WHERE status='open'"

# Performance
duckdb data/market_data.duckdb -box -c "
SELECT exchange, total_value, open_positions, total_trades, 
       ROUND(win_rate * 100, 1) as win_rate_pct, 
       total_pnl, sharpe_ratio
FROM portfolio_state"
```

## 🔄 Comandos do Scheduler

```bash
# Executar uma vez (teste)
python engines/pipeline_scheduler.py --test

# Produção (24/7)
python engines/pipeline_scheduler.py

# Desabilitar execução (só monitorar)
python engines/pipeline_scheduler.py --disable-execution

# Desabilitar componentes específicos
python engines/pipeline_scheduler.py \
  --disable-news \
  --disable-sentiment

# Background (nohup)
nohup python engines/pipeline_scheduler.py > scheduler.out 2>&1 &

# Background (screen)
screen -S trading
python engines/pipeline_scheduler.py
# Ctrl+A D para detach
# screen -r trading para reattach
```

## 🐛 Troubleshooting

### Database locked
```bash
pkill -f duckdb
duckdb data/market_data.duckdb -c "CHECKPOINT"
```

### FinBERT não funciona
```bash
pip install --upgrade transformers torch
python -c "from transformers import AutoModelForSequenceClassification; AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')"
```

### Alpaca API erro
```bash
# Verificar credenciais
python -c "
from alpaca.trading.client import TradingClient
client = TradingClient('API_KEY', 'API_SECRET', paper=True)
print(client.get_account())"
```

### Reset completo
```bash
# CUIDADO: Apaga todos os dados
rm data/market_data.duckdb
./scripts/setup_pipeline.sh
```

## 📚 Documentação Completa

- [Guia de Uso Detalhado](docs/USAGE_GUIDE.md)
- [Integração Backtrader](docs/BACKTRADER_INTEGRATION.md)
- [Arquitetura de Dados](docs/DATA_ARCHITECTURE.md)
- [Engines](docs/README_ENGINES.md)
- [Modelo FinBERT](docs/FINBERT_ENGINE.md)

## ⚠️ Avisos

- **Paper Trading Only**: Sistema usa apenas contas de simulação
- **Não é Conselho Financeiro**: Use por sua conta e risco
- **Monitorar Sempre**: Acompanhe os resultados regularmente
- **Rate Limits**: Respeite limites das APIs
- **Backup**: Faça backup do database periodicamente

## 🤝 Contribuindo

Sistema baseado em [backtrader](https://www.backtrader.com/) com engines customizados.

## 📄 Licença

Ver [LICENSE](LICENSE)

---

**Status**: ✅ Produção Ready | **Paper Trading**: Alpaca + Binance Testnet | **Modelo**: FinBERT (ProsusAI)
