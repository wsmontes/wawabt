#!/bin/bash
# Teste rápido de todos os componentes da pipeline

set -e

echo "==================================="
echo "   Pipeline Quick Test"
echo "==================================="

# Verificar venv
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Ative o ambiente virtual primeiro:"
    echo "   source venv/bin/activate"
    exit 1
fi

echo ""
echo "1️⃣  Testando RSSEngine..."
python -c "
from engines.rss import RSSEngine
rss = RSSEngine()
feeds = rss.fetch_all_feeds()
print(f'✓ Coletou {len(feeds)} entradas de RSS')
" || echo "❌ RSSEngine falhou"

echo ""
echo "2️⃣  Testando ConnectorEngine (Alpaca News)..."
python -c "
from engines.connector import ConnectorEngine
conn = ConnectorEngine()
try:
    news = conn.get_alpaca_news(symbols=['AAPL'], limit=5)
    print(f'✓ Coletou {len(news)} notícias da Alpaca')
except Exception as e:
    print(f'⚠️  Alpaca API: {e}')
    print('   (Configure credenciais em config/paper_trading.json)')
" || echo "❌ ConnectorEngine falhou"

echo ""
echo "3️⃣  Testando FinBERTEngine..."
python -c "
from engines.finbert import FinBERTEngine
fb = FinBERTEngine()
result = fb.analyze_text('Apple reports strong quarterly earnings with record revenue')
print(f'✓ Sentiment: {result[\"sentiment\"]} (score: {result[\"sentiment_score\"]:.2f}, conf: {result[\"confidence\"]:.2f})')
" || echo "❌ FinBERTEngine falhou"

echo ""
echo "4️⃣  Testando SmartDatabaseManager..."
python -c "
from engines.smart_db import SmartDatabaseManager
db = SmartDatabaseManager()
result = db.conn.execute('SELECT COUNT(*) FROM news_raw').fetchone()
print(f'✓ Database OK - {result[0] if result else 0} notícias no banco')
" || echo "❌ SmartDatabaseManager falhou"

echo ""
echo "5️⃣  Testando NewsCollectorPipeline..."
python -c "
from engines.news_collector_pipeline import NewsCollectorPipeline
pipeline = NewsCollectorPipeline()
result = pipeline.run(limit=5)
print(f'✓ NewsCollector OK - {result[\"news_collected\"]} notícias coletadas, {result[\"news_saved\"]} salvas')
" || echo "❌ NewsCollectorPipeline falhou"

echo ""
echo "6️⃣  Testando SentimentAnalysisPipeline..."
python -c "
from engines.sentiment_pipeline import SentimentAnalysisPipeline
pipeline = SentimentAnalysisPipeline()
result = pipeline.run(limit=5)
print(f'✓ SentimentPipeline OK - {result[\"news_analyzed\"]} notícias analisadas')
" || echo "❌ SentimentAnalysisPipeline falhou"

echo ""
echo "7️⃣  Testando RealtimeAlertManager..."
python -c "
from engines.realtime_alert_manager import RealtimeAlertManager
manager = RealtimeAlertManager()
result = manager.run()
print(f'✓ AlertManager OK - {result[\"alerts_generated\"]} alertas gerados')
" || echo "❌ RealtimeAlertManager falhou"

echo ""
echo "8️⃣  Testando AlpacaStore (se credenciais configuradas)..."
python -c "
try:
    import json
    with open('config/paper_trading.json') as f:
        config = json.load(f)
    
    if config['alpaca']['api_key'] and config['alpaca']['api_secret']:
        from backtrader.stores.alpacastore import AlpacaStore
        store = AlpacaStore(
            api_key=config['alpaca']['api_key'],
            api_secret=config['alpaca']['api_secret'],
            paper=True
        )
        store.start()
        cash = store.get_cash()
        print(f'✓ AlpacaStore OK - Buying Power: \${cash:.2f}')
    else:
        print('⚠️  AlpacaStore - Configure credenciais em config/paper_trading.json')
except Exception as e:
    print(f'⚠️  AlpacaStore: {e}')
" || echo "❌ AlpacaStore falhou"

echo ""
echo "9️⃣  Testando CCXTStore (se credenciais configuradas)..."
python -c "
try:
    import json
    with open('config/paper_trading.json') as f:
        config = json.load(f)
    
    if config['binance']['api_key'] and config['binance']['api_secret']:
        from backtrader.stores.ccxtstore import CCXTStore
        store = CCXTStore(
            exchange='binance',
            api_key=config['binance']['api_key'],
            secret=config['binance']['api_secret'],
            sandbox=True
        )
        store.start()
        balance = store.get_balance()
        usdt = balance.get('USDT', {}).get('free', 0)
        print(f'✓ CCXTStore OK - USDT Balance: {usdt:.2f}')
    else:
        print('⚠️  CCXTStore - Configure credenciais em config/paper_trading.json')
except Exception as e:
    print(f'⚠️  CCXTStore: {e}')
" || echo "❌ CCXTStore falhou"

echo ""
echo "🔟 Testando PipelineScheduler..."
python -c "
from engines.pipeline_scheduler import PipelineScheduler
scheduler = PipelineScheduler()
print('✓ PipelineScheduler OK - Scheduler inicializado')
scheduler.scheduler.print_jobs()
" || echo "❌ PipelineScheduler falhou"

echo ""
echo "==================================="
echo "✅ Testes concluídos!"
echo "==================================="
echo ""
echo "Para executar pipeline completo:"
echo "  python engines/pipeline_scheduler.py --test"
echo ""
echo "Para monitorar resultados:"
echo "  ./scripts/monitor.sh"
echo ""
