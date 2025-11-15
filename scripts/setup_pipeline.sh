#!/bin/bash
# Setup inicial da pipeline de trading

set -e

echo "==================================="
echo "Setup Pipeline de Trading Automático"
echo "==================================="

# Verificar se está no venv
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Ative o ambiente virtual primeiro:"
    echo "   source venv/bin/activate"
    exit 1
fi

echo ""
echo "1️⃣  Instalando dependências..."
pip install -q apscheduler
echo "✓ APScheduler instalado"

echo ""
echo "2️⃣  Verificando dependências críticas..."
python -c "
import sys
try:
    import alpaca
    print('✓ alpaca-py')
except ImportError:
    print('❌ alpaca-py não encontrado')
    sys.exit(1)

try:
    import ccxt
    print('✓ ccxt')
except ImportError:
    print('❌ ccxt não encontrado')
    sys.exit(1)

try:
    import feedparser
    print('✓ feedparser')
except ImportError:
    print('❌ feedparser não encontrado')
    sys.exit(1)

try:
    import transformers
    print('✓ transformers')
except ImportError:
    print('❌ transformers não encontrado')
    sys.exit(1)
"

echo ""
echo "3️⃣  Baixando modelo FinBERT (pode demorar)..."
python -c "
from transformers import AutoTokenizer, AutoModelForSequenceClassification
print('Downloading tokenizer...')
AutoTokenizer.from_pretrained('ProsusAI/finbert')
print('Downloading model...')
AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')
print('✓ Modelo FinBERT baixado')
"

echo ""
echo "4️⃣  Criando diretórios necessários..."
mkdir -p logs
mkdir -p data/market
mkdir -p data/news
mkdir -p data/analysis
echo "✓ Diretórios criados"

echo ""
echo "5️⃣  Inicializando database..."
if [ ! -f "data/market_data.duckdb" ]; then
    python -c "
import duckdb
conn = duckdb.connect('data/market_data.duckdb')

# Criar tabelas
conn.execute('''
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
    status VARCHAR DEFAULT 'pending'
)
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS news_sentiment (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR,
    sentiment VARCHAR,
    sentiment_score DOUBLE,
    confidence DOUBLE,
    analyzed_at TIMESTAMP
)
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS news_by_symbol (
    id VARCHAR PRIMARY KEY,
    news_id VARCHAR,
    symbol VARCHAR,
    sentiment VARCHAR,
    sentiment_score DOUBLE,
    confidence DOUBLE,
    analyzed_at TIMESTAMP
)
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS realtime_alerts (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR,
    signal_type VARCHAR,
    signal_strength DOUBLE,
    sentiment_score DOUBLE,
    confidence DOUBLE,
    news_count INTEGER,
    generated_at TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR DEFAULT 'active',
    exchange VARCHAR
)
''')

conn.execute('''
CREATE TABLE IF NOT EXISTS paper_trades (
    id VARCHAR PRIMARY KEY,
    alert_id VARCHAR,
    symbol VARCHAR,
    exchange VARCHAR,
    side VARCHAR,
    quantity DOUBLE,
    entry_price DOUBLE,
    stop_loss DOUBLE,
    take_profit DOUBLE,
    status VARCHAR DEFAULT 'open',
    opened_at TIMESTAMP,
    closed_at TIMESTAMP,
    exit_price DOUBLE,
    pnl DOUBLE,
    pnl_pct DOUBLE,
    exit_reason VARCHAR,
    holding_period_hours DOUBLE
)
''')

conn.execute('''
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
)
''')

conn.close()
print('✓ Database inicializado')
"
else
    echo "✓ Database já existe"
fi

echo ""
echo "6️⃣  Testando componentes..."
echo -n "   NewsCollector... "
python -c "from engines.news_collector_pipeline import NewsCollectorPipeline; p = NewsCollectorPipeline(); print('✓')"

echo -n "   SentimentPipeline... "
python -c "from engines.sentiment_pipeline import SentimentAnalysisPipeline; p = SentimentAnalysisPipeline(); print('✓')"

echo -n "   AlertManager... "
python -c "from engines.realtime_alert_manager import RealtimeAlertManager; m = RealtimeAlertManager(); print('✓')"

echo -n "   SignalExecution... "
python -c "from engines.signal_execution import SignalExecutionManager; m = SignalExecutionManager(); print('✓')"

echo -n "   PerformanceTracker... "
python -c "from engines.performance_tracker import PerformanceTracker; t = PerformanceTracker(); print('✓')"

echo ""
echo "==================================="
echo "✅ Setup concluído com sucesso!"
echo "==================================="
echo ""
echo "Próximos passos:"
echo ""
echo "1. Configure suas credenciais em config/paper_trading.json:"
echo "   - Alpaca: https://alpaca.markets/ (Paper Trading)"
echo "   - Binance: https://testnet.binance.vision/"
echo ""
echo "2. Teste os componentes individualmente:"
echo "   python engines/news_collector_pipeline.py"
echo "   python engines/sentiment_pipeline.py"
echo "   python engines/realtime_alert_manager.py"
echo ""
echo "3. Execute o scheduler em modo teste:"
echo "   python engines/pipeline_scheduler.py --test"
echo ""
echo "4. Inicie em modo produção:"
echo "   python engines/pipeline_scheduler.py"
echo ""
echo "📚 Ver guia completo: docs/USAGE_GUIDE.md"
echo ""
