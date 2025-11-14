"""
Script para buscar dados históricos dos símbolos mais mencionados nas notícias
que ainda não têm dados de mercado no banco.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
import duckdb
from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager

def identify_missing_symbols():
    """Identifica símbolos mencionados mas sem dados de mercado"""
    print("="*80)
    print("🔍 IDENTIFICANDO SÍMBOLOS MAIS MENCIONADOS SEM DADOS")
    print("="*80)
    
    conn = duckdb.connect('data/market_data.duckdb')
    
    # Carregar análise de impacto para ver símbolos mencionados
    with open('news_market_impact_report.json', 'r') as f:
        report = json.load(f)
    
    # Símbolos que já temos dados
    market_query = """
    SELECT table_name FROM information_schema.tables 
    WHERE table_name LIKE 'market_%'
    """
    
    market_tables = conn.execute(market_query).fetchdf()
    
    # Extrair símbolos das tabelas de mercado
    existing_symbols = set()
    for table in market_tables['table_name']:
        parts = table.split('_')
        if len(parts) >= 3:
            # market_source_SYMBOL_interval
            if parts[1] in ['yahoo', 'binance', 'Binance']:
                symbol = '_'.join(parts[2:-1])  # Pode ter underscore no meio
                existing_symbols.add(symbol.upper())
    
    print(f"\n💹 Símbolos com dados de mercado: {len(existing_symbols)}")
    
    # Símbolos do relatório de impacto
    impact_symbols = Counter()
    for item in report['impact_data']:
        impact_symbols[item['symbol']] += 1
    
    print(f"\n📰 Símbolos no relatório de impacto: {len(impact_symbols)}")
    print(f"   Total de menções: {sum(impact_symbols.values()):,}")
    
    # Símbolos faltantes (prioritários - stocks principais e top cryptos)
    priority_stocks = [
        'GOOGL', 'META', 'AMZN', 'NVDA', 'AAPL', 'TSLA', 'MSFT',
        'NFLX', 'AMD', 'INTC', 'QCOM', 'CRM', 'ORCL', 'ADBE',
        'PYPL', 'SQ', 'COIN', 'SHOP', 'UBER', 'ABNB',
        'JPM', 'BAC', 'GS', 'MS', 'WFC', 'C',
        'JNJ', 'PFE', 'UNH', 'ABBV', 'TMO', 'DHR',
        'XOM', 'CVX', 'COP', 'SLB',
        'WMT', 'HD', 'NKE', 'MCD', 'SBUX', 'DIS'
    ]
    
    priority_crypto = [
        'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'DOGE',
        'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'ETC',
        'NEAR', 'ALGO', 'FIL', 'VET', 'SAND', 'MANA', 'AXS'
    ]
    
    # Separar em crypto e stocks
    missing_stocks = []
    missing_crypto = []
    
    for symbol in priority_stocks:
        if symbol not in existing_symbols and symbol.upper() not in existing_symbols:
            mentions = impact_symbols.get(symbol, 0)
            missing_stocks.append((symbol, mentions))
    
    for symbol in priority_crypto:
        # Crypto pode estar como SYMBOL ou SYMBOLUSDT
        if (symbol not in existing_symbols and 
            f"{symbol}USDT" not in existing_symbols and
            f"{symbol}_USD" not in existing_symbols):
            mentions = impact_symbols.get(symbol, 0)
            missing_crypto.append((symbol, mentions))
    
    # Ordenar por menções
    missing_stocks.sort(key=lambda x: x[1], reverse=True)
    missing_crypto.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 SÍMBOLOS PRIORITÁRIOS FALTANTES:")
    print(f"   Stocks: {len(missing_stocks)}")
    print(f"   Crypto: {len(missing_crypto)}")
    
    if missing_stocks:
        print(f"\n🏢 TOP STOCKS FALTANDO:")
        for symbol, mentions in missing_stocks[:20]:
            print(f"      {symbol}: {mentions} menções")
    
    if missing_crypto:
        print(f"\n₿ TOP CRYPTO FALTANDO:")
        for symbol, mentions in missing_crypto[:20]:
            print(f"      {symbol}: {mentions} menções")
    
    conn.close()
    
    return missing_stocks, missing_crypto


def fetch_historical_data(symbols, source='yahoo', symbol_type='stock'):
    """Busca dados históricos para os símbolos"""
    print(f"\n{'='*80}")
    print(f"📥 BUSCANDO DADOS HISTÓRICOS ({symbol_type.upper()})")
    print(f"{'='*80}")
    
    # Usar connector sem auto-save para evitar problemas
    connector = ConnectorEngine(use_smart_db=False)
    smart_db = SmartDatabaseManager()
    
    # Período: últimos 5 anos
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5*365)
    
    success = 0
    failed = 0
    
    for symbol, mentions in symbols:
        try:
            print(f"\n📊 {symbol} ({mentions} menções)...")
            
            if source == 'yahoo':
                # Para stocks: buscar direto
                # Para crypto: adicionar -USD
                ticker = f"{symbol}-USD" if symbol_type == 'crypto' else symbol
                
                df = connector.get_yahoo_data(
                    ticker,
                    start=start_date.strftime('%Y-%m-%d'),
                    end=end_date.strftime('%Y-%m-%d'),
                    interval='1d'
                )
            
            elif source == 'binance':
                # Para crypto: adicionar USDT
                ticker = f"{symbol}USDT"
                
                df = connector.get_binance_data(
                    symbol=ticker,
                    interval='1d',
                    start_time=start_date,
                    end_time=end_date
                )
            
            if df is not None and len(df) > 0:
                # Salvar manualmente no smart_db
                try:
                    smart_db.save_market_data(
                        df=df,
                        symbol=ticker if source == 'yahoo' else symbol,
                        source=f'yahoo_finance' if source == 'yahoo' else 'binance',
                        interval='1d'
                    )
                    print(f"   ✅ {len(df)} registros obtidos e salvos")
                    success += 1
                except Exception as save_error:
                    print(f"   ⚠️ Dados obtidos mas erro ao salvar: {save_error}")
                    failed += 1
            else:
                print(f"   ⚠️ Nenhum dado retornado")
                failed += 1
                
        except Exception as e:
            print(f"   ❌ Erro: {str(e)}")
            failed += 1
            continue
    
    print(f"\n{'='*80}")
    print(f"📈 RESUMO ({symbol_type.upper()}):")
    print(f"   ✅ Sucesso: {success}")
    print(f"   ❌ Falha: {failed}")
    print(f"   Total: {success + failed}")
    print(f"{'='*80}")
    
    return success, failed


def main():
    print("\n" + "="*80)
    print("🚀 FETCH MISSING SYMBOLS - EXPANSÃO DE DADOS DE MERCADO")
    print("="*80)
    
    # 1. Identificar símbolos faltantes
    missing_stocks, missing_crypto = identify_missing_symbols()
    
    if not missing_stocks and not missing_crypto:
        print("\n✅ Todos os símbolos prioritários já têm dados!")
        return
    
    # 2. Buscar dados históricos
    total_success = 0
    total_failed = 0
    
    # Stocks via Yahoo Finance
    if missing_stocks:
        print(f"\n🔄 Processando {len(missing_stocks)} stocks...")
        s, f = fetch_historical_data(missing_stocks, source='yahoo', symbol_type='stock')
        total_success += s
        total_failed += f
    
    # Crypto via Yahoo Finance (mais confiável que Binance para histórico longo)
    if missing_crypto:
        print(f"\n🔄 Processando {len(missing_crypto)} cryptos (Yahoo)...")
        s, f = fetch_historical_data(missing_crypto, source='yahoo', symbol_type='crypto')
        total_success += s
        total_failed += f
        
        # Tentar Binance para os que falharam no Yahoo
        failed_crypto = [(sym, men) for sym, men in missing_crypto]
        if failed_crypto and total_failed > 0:
            print(f"\n🔄 Tentando novamente via Binance...")
            s2, f2 = fetch_historical_data(failed_crypto, source='binance', symbol_type='crypto')
            total_success += s2
            total_failed += f2
    
    # 3. Sumário final
    print("\n" + "="*80)
    print("🎯 RESULTADO FINAL")
    print("="*80)
    print(f"\n   ✅ Total de sucesso: {total_success}")
    print(f"   ❌ Total de falhas: {total_failed}")
    print(f"   📈 Símbolos processados: {total_success + total_failed}")
    
    if total_success > 0:
        print(f"\n   💡 Próximo passo: Re-executar analyze_news_market_impact.py")
        print(f"      para incluir os novos dados na análise!")
    
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
