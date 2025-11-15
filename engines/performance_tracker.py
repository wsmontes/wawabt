#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# PerformanceTracker: Monitor paper trades e calcula PnL
# - Monitora paper_trades (status='open')
# - Consulta preços atuais via ConnectorEngine
# - Calcula unrealized PnL
# - Fecha posições se hit stop-loss ou take-profit
# - Atualiza portfolio_state
# - Calcula métricas (Sharpe, win rate, etc)
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """
    Monitor de performance para paper trading.
    
    Responsabilidades:
    1. Carregar paper_trades com status='open'
    2. Obter preços atuais via ConnectorEngine
    3. Calcular unrealized PnL
    4. Verificar stop-loss / take-profit
    5. Fechar posições automaticamente
    6. Atualizar portfolio_state
    7. Calcular métricas de performance
    
    NÃO duplica código - usa ConnectorEngine para preços.
    """
    
    def __init__(self, connector_config: str = 'config/connector.json'):
        """
        Initialize PerformanceTracker.
        
        Args:
            connector_config: Path to connector configuration
        """
        # Initialize engines (reuse existing)
        logger.info("Initializing engines...")
        
        self.connector = ConnectorEngine(
            config_path=connector_config,
            use_smart_db=True
        )
        
        self.db = SmartDatabaseManager()
        
        # Performance metrics cache
        self.metrics = {
            'alpaca': {},
            'binance': {}
        }
        
        logger.info("PerformanceTracker initialized")
    
    def run(self):
        """
        Execute tracking cycle:
        1. Load open positions
        2. Get current prices
        3. Calculate PnL
        4. Check stop-loss/take-profit
        5. Close positions if needed
        6. Update portfolio state
        7. Calculate metrics
        """
        logger.info("=== PerformanceTracker.run() ===")
        
        # 1. Load open trades
        open_trades = self._load_open_trades()
        
        if open_trades.empty:
            logger.info("No open trades to monitor")
            self._update_portfolio_state_empty()
            return
        
        logger.info(f"Monitoring {len(open_trades)} open trades")
        
        # 2. Update prices and calculate PnL
        updated_trades = self._update_prices_and_pnl(open_trades)
        
        # 3. Check for positions to close
        closed_trades = self._check_exit_conditions(updated_trades)
        
        if not closed_trades.empty:
            logger.info(f"Closing {len(closed_trades)} trades")
            self._close_trades(closed_trades)
        
        # 4. Save updated trades
        self._save_trade_updates(updated_trades)
        
        # 5. Update portfolio state
        self._update_portfolio_state(updated_trades)
        
        # 6. Calculate performance metrics
        self._calculate_metrics()
        
        logger.info("Tracking cycle complete")
    
    def _load_open_trades(self) -> pd.DataFrame:
        """Load all open paper trades"""
        query = """
        SELECT 
            id,
            exchange,
            symbol,
            side,
            entry_price,
            position_size,
            stop_loss,
            take_profit,
            entry_time,
            sentiment_score,
            confidence,
            signal_id
        FROM paper_trades
        WHERE status = 'open'
        ORDER BY entry_time ASC
        """
        
        try:
            return self.db.query(query)
        except Exception as e:
            logger.error(f"Error loading open trades: {e}")
            return pd.DataFrame()
    
    def _update_prices_and_pnl(self, df: pd.DataFrame) -> pd.DataFrame:
        """Update current prices and calculate unrealized PnL"""
        if df.empty:
            return df
        
        df = df.copy()
        df['current_price'] = 0.0
        df['unrealized_pnl'] = 0.0
        df['unrealized_pnl_pct'] = 0.0
        
        for idx, trade in df.iterrows():
            try:
                # Get current price based on exchange
                if trade['exchange'] == 'alpaca':
                    current_price = self._get_alpaca_price(trade['symbol'])
                elif trade['exchange'] == 'binance':
                    current_price = self._get_binance_price(trade['symbol'])
                else:
                    logger.warning(f"Unknown exchange: {trade['exchange']}")
                    continue
                
                if current_price <= 0:
                    logger.warning(f"Invalid price for {trade['symbol']}: {current_price}")
                    continue
                
                # Calculate PnL
                entry_price = float(trade['entry_price'])
                position_size = float(trade['position_size'])
                
                if trade['side'] == 'buy' or trade['side'] == 'long':
                    # Long position: profit if price goes up
                    pnl = (current_price - entry_price) * position_size
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                else:
                    # Short position: profit if price goes down
                    pnl = (entry_price - current_price) * position_size
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                
                # Update DataFrame
                df.at[idx, 'current_price'] = current_price
                df.at[idx, 'unrealized_pnl'] = pnl
                df.at[idx, 'unrealized_pnl_pct'] = pnl_pct
                
                logger.debug(f"{trade['symbol']}: entry=${entry_price:.2f}, "
                           f"current=${current_price:.2f}, "
                           f"PnL=${pnl:.2f} ({pnl_pct:+.2f}%)")
                
            except Exception as e:
                logger.error(f"Error updating {trade['symbol']}: {e}")
                continue
        
        return df
    
    def _get_alpaca_price(self, symbol: str) -> float:
        """Get current price from Alpaca using ConnectorEngine"""
        try:
            # Use get_alpaca_latest_bar (já existe no ConnectorEngine)
            latest = self.connector.get_alpaca_latest_bar(symbol)
            
            # latest é um dict com symbol -> BarData
            if symbol in latest:
                bar = latest[symbol]
                return float(bar.close)
            
            logger.warning(f"No price data for {symbol} from Alpaca")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error fetching Alpaca price for {symbol}: {e}")
            return 0.0
    
    def _get_binance_price(self, symbol: str) -> float:
        """Get current price from Binance using ConnectorEngine"""
        try:
            # Use get_ccxt_ticker (já existe no ConnectorEngine)
            ticker = self.connector.get_ccxt_ticker(symbol, exchange='binance')
            
            if 'last' in ticker:
                return float(ticker['last'])
            elif 'close' in ticker:
                return float(ticker['close'])
            
            logger.warning(f"No price data for {symbol} from Binance")
            return 0.0
            
        except Exception as e:
            logger.error(f"Error fetching Binance price for {symbol}: {e}")
            return 0.0
    
    def _check_exit_conditions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Check which positions should be closed (stop-loss or take-profit hit)"""
        if df.empty:
            return pd.DataFrame()
        
        to_close = []
        
        for idx, trade in df.iterrows():
            current_price = trade.get('current_price', 0)
            
            if current_price <= 0:
                continue
            
            stop_loss = float(trade['stop_loss'])
            take_profit = float(trade['take_profit'])
            
            exit_reason = None
            
            if trade['side'] == 'buy' or trade['side'] == 'long':
                # Long position
                if current_price <= stop_loss:
                    exit_reason = 'stop_loss'
                elif current_price >= take_profit:
                    exit_reason = 'take_profit'
            else:
                # Short position (inverted logic)
                if current_price >= stop_loss:
                    exit_reason = 'stop_loss'
                elif current_price <= take_profit:
                    exit_reason = 'take_profit'
            
            if exit_reason:
                trade_dict = trade.to_dict()
                trade_dict['exit_reason'] = exit_reason
                to_close.append(trade_dict)
                
                logger.info(f"Exit trigger: {trade['symbol']} - {exit_reason} "
                          f"(entry=${trade['entry_price']:.2f}, "
                          f"current=${current_price:.2f}, "
                          f"PnL=${trade['unrealized_pnl']:.2f})")
        
        return pd.DataFrame(to_close)
    
    def _close_trades(self, df: pd.DataFrame):
        """Close trades by updating database"""
        if df.empty:
            return
        
        now = datetime.now()
        
        for _, trade in df.iterrows():
            # Calculate holding period
            entry_time = pd.to_datetime(trade['entry_time'])
            holding_period = (now - entry_time).total_seconds() / 3600  # hours
            
            # Update query
            update_query = f"""
            UPDATE paper_trades
            SET 
                status = 'closed',
                exit_price = {trade['current_price']},
                exit_time = '{now.isoformat()}',
                pnl = {trade['unrealized_pnl']},
                pnl_pct = {trade['unrealized_pnl_pct']},
                exit_reason = '{trade['exit_reason']}',
                holding_period_hours = {holding_period:.2f}
            WHERE id = '{trade['id']}'
            """
            
            try:
                self.db.execute(update_query)
                logger.info(f"Closed trade {trade['id']}: {trade['symbol']} "
                          f"PnL=${trade['unrealized_pnl']:.2f} ({trade['unrealized_pnl_pct']:+.2f}%) "
                          f"Reason={trade['exit_reason']}")
            except Exception as e:
                logger.error(f"Error closing trade {trade['id']}: {e}")
    
    def _save_trade_updates(self, df: pd.DataFrame):
        """Save unrealized PnL updates for open trades"""
        if df.empty:
            return
        
        # Filter only trades still open (not in closed list)
        open_trades = df[df.get('exit_reason', '') == '']
        
        if open_trades.empty:
            return
        
        now = datetime.now()
        
        for _, trade in open_trades.iterrows():
            update_query = f"""
            UPDATE paper_trades
            SET 
                current_price = {trade['current_price']},
                unrealized_pnl = {trade['unrealized_pnl']},
                unrealized_pnl_pct = {trade['unrealized_pnl_pct']},
                last_updated = '{now.isoformat()}'
            WHERE id = '{trade['id']}'
            """
            
            try:
                self.db.execute(update_query)
            except Exception as e:
                logger.error(f"Error updating trade {trade['id']}: {e}")
    
    def _update_portfolio_state(self, df: pd.DataFrame):
        """Update portfolio_state table with current positions"""
        if df.empty:
            self._update_portfolio_state_empty()
            return
        
        timestamp = datetime.now()
        
        # Aggregate by exchange
        for exchange in df['exchange'].unique():
            exchange_trades = df[df['exchange'] == exchange]
            
            # Calculate total values
            total_position_value = 0.0
            total_unrealized_pnl = 0.0
            
            rows = []
            
            for _, trade in exchange_trades.iterrows():
                # Skip if no current price
                if trade.get('current_price', 0) <= 0:
                    continue
                
                position_value = trade['current_price'] * trade['position_size']
                total_position_value += position_value
                total_unrealized_pnl += trade.get('unrealized_pnl', 0)
                
                # Record individual position
                position_row = {
                    'timestamp': timestamp,
                    'exchange': exchange,
                    'symbol': trade['symbol'],
                    'position_size': trade['position_size'],
                    'avg_entry_price': trade['entry_price'],
                    'current_price': trade['current_price'],
                    'unrealized_pnl': trade.get('unrealized_pnl', 0),
                    'total_cash': 0,  # Will be filled below
                    'total_value': 0   # Will be filled below
                }
                rows.append(position_row)
            
            # Add summary row
            summary_row = {
                'timestamp': timestamp,
                'exchange': exchange,
                'symbol': 'TOTAL',
                'position_size': len(exchange_trades),
                'avg_entry_price': 0,
                'current_price': 0,
                'unrealized_pnl': total_unrealized_pnl,
                'total_cash': 0,  # TODO: Get from broker
                'total_value': total_position_value + total_unrealized_pnl
            }
            rows.append(summary_row)
            
            # Save to database
            if rows:
                portfolio_df = pd.DataFrame(rows)
                try:
                    self.db.save_dataframe(portfolio_df, 'portfolio_state', mode='append')
                except Exception as e:
                    logger.error(f"Error saving portfolio state for {exchange}: {e}")
        
        logger.info("Portfolio state updated")
    
    def _update_portfolio_state_empty(self):
        """Update portfolio state when no positions"""
        timestamp = datetime.now()
        
        for exchange in ['alpaca', 'binance']:
            row = {
                'timestamp': timestamp,
                'exchange': exchange,
                'symbol': 'TOTAL',
                'position_size': 0,
                'avg_entry_price': 0,
                'current_price': 0,
                'unrealized_pnl': 0,
                'total_cash': 0,
                'total_value': 0
            }
            
            try:
                self.db.save_dataframe(pd.DataFrame([row]), 'portfolio_state', mode='append')
            except Exception as e:
                logger.error(f"Error saving empty portfolio state: {e}")
    
    def _calculate_metrics(self):
        """Calculate performance metrics (Sharpe, win rate, etc)"""
        # Query all closed trades
        query = """
        SELECT 
            exchange,
            pnl,
            pnl_pct,
            holding_period_hours,
            exit_reason
        FROM paper_trades
        WHERE status = 'closed'
        AND exit_time >= datetime('now', '-30 days')
        """
        
        try:
            closed_trades = self.db.query(query)
            
            if closed_trades.empty:
                logger.info("No closed trades for metrics calculation")
                return
            
            # Calculate metrics per exchange
            for exchange in closed_trades['exchange'].unique():
                exchange_trades = closed_trades[closed_trades['exchange'] == exchange]
                
                metrics = self._calculate_exchange_metrics(exchange_trades)
                self.metrics[exchange] = metrics
                
                logger.info(f"{exchange.upper()} Metrics (30d):")
                logger.info(f"  Total trades: {metrics['total_trades']}")
                logger.info(f"  Win rate: {metrics['win_rate']:.1f}%")
                logger.info(f"  Avg PnL: ${metrics['avg_pnl']:.2f}")
                logger.info(f"  Total PnL: ${metrics['total_pnl']:.2f}")
                logger.info(f"  Sharpe: {metrics['sharpe']:.2f}")
                
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
    
    def _calculate_exchange_metrics(self, df: pd.DataFrame) -> Dict:
        """Calculate metrics for a specific exchange"""
        if df.empty:
            return {}
        
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df['pnl'].sum()
        avg_pnl = df['pnl'].mean()
        
        # Sharpe ratio (simplified: returns / std of returns)
        returns = df['pnl_pct'].values
        sharpe = (returns.mean() / returns.std()) if returns.std() > 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': total_trades - winning_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'sharpe': sharpe,
            'avg_holding_hours': df['holding_period_hours'].mean()
        }


def main():
    """Test execution"""
    tracker = PerformanceTracker()
    tracker.run()


if __name__ == '__main__':
    main()
