#!/usr/bin/env python3
"""
Quick Status Check - Pipeline Trading
Verifica status rápido de todos os componentes
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.smart_db import SmartDatabaseManager
from datetime import datetime, timedelta

def colorize(text, color):
    colors = {
        'red': '\033[0;31m',
        'green': '\033[0;32m',
        'yellow': '\033[1;33m',
        'blue': '\033[0;34m',
        'nc': '\033[0m'
    }
    return f"{colors.get(color, '')}{text}{colors['nc']}"

def print_header(title):
    print(f"\n{colorize('=' * 50, 'blue')}")
    print(colorize(f"  {title}", 'blue'))
    print(colorize('=' * 50, 'blue'))

def main():
    try:
        db = SmartDatabaseManager()
        
        print_header("Pipeline Status Dashboard")
        
        # News Status
        print(f"\n{colorize('📰 Notícias', 'yellow')}")
        news_stats = db.conn.execute("""
            SELECT 
                status,
                COUNT(*) as count,
                MAX(published_at) as last_published
            FROM news_raw
            GROUP BY status
        """).fetchall()
        
        if news_stats:
            for status, count, last_pub in news_stats:
                print(f"  {status:10s}: {count:5d} notícias (última: {last_pub or 'N/A'})")
        else:
            print(colorize("  Nenhuma notícia coletada ainda", 'red'))
        
        # Recent Sentiments
        print(f"\n{colorize('💭 Sentimentos Recentes', 'yellow')}")
        sentiments = db.conn.execute("""
            SELECT 
                symbol,
                sentiment,
                ROUND(sentiment_score, 3) as score,
                ROUND(confidence, 3) as conf
            FROM news_by_symbol
            ORDER BY analyzed_at DESC
            LIMIT 5
        """).fetchall()
        
        if sentiments:
            for symbol, sentiment, score, conf in sentiments:
                emoji = '📈' if sentiment == 'positive' else '📉' if sentiment == 'negative' else '➡️'
                print(f"  {emoji} {symbol:8s} {sentiment:8s} score={score:+.3f} conf={conf:.3f}")
        else:
            print(colorize("  Nenhum sentiment analisado ainda", 'red'))
        
        # Active Alerts
        print(f"\n{colorize('🚨 Alertas Ativos', 'yellow')}")
        alerts = db.conn.execute("""
            SELECT 
                symbol,
                signal_type,
                ROUND(signal_strength, 3) as strength,
                ROUND(confidence, 3) as conf,
                exchange
            FROM realtime_alerts
            WHERE status = 'active'
            ORDER BY signal_strength DESC
            LIMIT 5
        """).fetchall()
        
        if alerts:
            for symbol, signal, strength, conf, exchange in alerts:
                emoji = '🟢' if signal == 'BUY' else '🔴'
                print(f"  {emoji} {symbol:8s} {signal:4s} strength={strength:.3f} conf={conf:.3f} [{exchange}]")
        else:
            print(colorize("  Nenhum alerta ativo", 'green'))
        
        # Open Positions
        print(f"\n{colorize('📊 Posições Abertas', 'yellow')}")
        positions = db.conn.execute("""
            SELECT 
                symbol,
                side,
                ROUND(quantity, 4) as qty,
                ROUND(entry_price, 2) as entry,
                exchange
            FROM paper_trades
            WHERE status = 'open'
        """).fetchall()
        
        if positions:
            for symbol, side, qty, entry, exchange in positions:
                emoji = '🟢' if side == 'BUY' else '🔴'
                print(f"  {emoji} {symbol:8s} {side:4s} qty={qty:.4f} @{entry:.2f} [{exchange}]")
        else:
            print(colorize("  Nenhuma posição aberta", 'green'))
        
        # Portfolio Performance
        print(f"\n{colorize('💰 Performance', 'yellow')}")
        portfolio = db.conn.execute("""
            SELECT 
                exchange,
                ROUND(total_value, 2) as value,
                open_positions,
                total_trades,
                ROUND(win_rate * 100, 1) as win_rate_pct,
                ROUND(total_pnl, 2) as pnl,
                ROUND(sharpe_ratio, 2) as sharpe
            FROM portfolio_state
        """).fetchall()
        
        if portfolio:
            for exchange, value, positions, trades, win_rate, pnl, sharpe in portfolio:
                pnl_color = 'green' if pnl >= 0 else 'red'
                pnl_str = f"{pnl:+.2f}"
                print(f"  {exchange.upper():8s}: ${value:,.2f} | {positions} pos | {trades} trades | "
                      f"WR {win_rate:.1f}% | P&L {colorize(pnl_str, pnl_color)} | Sharpe {sharpe:.2f}")
        else:
            print(colorize("  Nenhum dado de portfolio", 'yellow'))
        
        # Summary
        total_news = db.conn.execute("SELECT COUNT(*) FROM news_raw").fetchone()[0]
        total_alerts = db.conn.execute("SELECT COUNT(*) FROM realtime_alerts WHERE status='active'").fetchone()[0]
        total_positions = db.conn.execute("SELECT COUNT(*) FROM paper_trades WHERE status='open'").fetchone()[0]
        total_pnl = db.conn.execute("SELECT COALESCE(SUM(total_pnl), 0) FROM portfolio_state").fetchone()[0]
        
        print_header("Resumo")
        print(f"  Notícias: {colorize(str(total_news), 'green')}")
        print(f"  Alertas Ativos: {colorize(str(total_alerts), 'yellow')}")
        print(f"  Posições Abertas: {colorize(str(total_positions), 'blue')}")
        
        pnl_color = 'green' if total_pnl >= 0 else 'red'
        print(f"  P&L Total: {colorize(f'${total_pnl:+.2f}', pnl_color)}")
        
        print(f"\n{colorize('=' * 50, 'blue')}\n")
        
    except Exception as e:
        print(colorize(f"❌ Erro: {e}", 'red'))
        sys.exit(1)

if __name__ == '__main__':
    main()
