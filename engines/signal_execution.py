#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# SignalExecutionManager: Orquestrador de execução de sinais de trading
# - Lê sinais da tabela realtime_alerts (status='active')
# - Valida sinais (confiança, timing, risk management)
# - Calcula position size usando Kelly Criterion
# - Roteia para Alpaca (stocks) ou Binance (crypto) via backtrader
# - Atualiza paper_trades e portfolio_state
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import backtrader as bt
import pandas as pd

from engines.smart_db import SmartDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalExecutionManager:
    """
    Gerenciador central de execução de sinais de trading.
    
    Responsabilidades:
    1. Carregar sinais ativos da tabela realtime_alerts
    2. Validar sinais (confiança, timing, risk rules)
    3. Calcular position size usando Kelly Criterion
    4. Rotear para broker correto (Alpaca/Binance)
    5. Executar ordem via backtrader Store/Broker
    6. Atualizar realtime_alerts (status='executed'/'rejected')
    7. Registrar em paper_trades
    8. Atualizar portfolio_state
    
    Config: config/paper_trading.json
    """
    
    def __init__(self, config_path: str = 'config/paper_trading.json'):
        """
        Initialize SignalExecutionManager.
        
        Args:
            config_path: Path to paper trading configuration
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.db = SmartDatabaseManager()
        
        # Trading components
        self.alpaca_store = None
        self.alpaca_broker = None
        self.ccxt_store = None
        self.ccxt_broker = None
        
        # State tracking
        self.portfolio_state = {
            'alpaca': {'cash': 0.0, 'positions': {}, 'total_value': 0.0},
            'binance': {'cash': 0.0, 'positions': {}, 'total_value': 0.0}
        }
        
        self._init_brokers()
        self._load_portfolio_state()
        
        logger.info("SignalExecutionManager initialized")
    
    def _load_config(self) -> Dict:
        """Load paper trading configuration"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        logger.info(f"Loaded config from {self.config_path}")
        return config
    
    def _init_brokers(self):
        """Initialize Alpaca and Binance brokers via backtrader"""
        # Alpaca (US Stocks)
        if self.config['alpaca']['enabled']:
            try:
                from backtrader.stores import AlpacaStore
                from backtrader.brokers import AlpacaBroker
                
                alpaca_cfg = self.config['alpaca']
                self.alpaca_store = AlpacaStore(
                    key_id=alpaca_cfg['api_key'],
                    secret_key=alpaca_cfg['api_secret'],
                    paper=alpaca_cfg['paper_trading'],
                    _debug=False
                )
                self.alpaca_broker = AlpacaBroker(store=self.alpaca_store)
                
                logger.info("Alpaca broker initialized (paper trading)")
            except ImportError:
                logger.warning("AlpacaStore not available (alpaca-py not installed)")
        
        # Binance (Crypto)
        if self.config['binance']['enabled']:
            try:
                from backtrader.stores import CCXTStore
                from backtrader.brokers import CCXTBroker
                
                binance_cfg = self.config['binance']
                self.ccxt_store = CCXTStore(
                    exchange='binance',
                    api_key=binance_cfg['api_key'],
                    api_secret=binance_cfg['api_secret'],
                    sandbox=binance_cfg['testnet'],
                    _debug=False
                )
                self.ccxt_broker = CCXTBroker(
                    store=self.ccxt_store,
                    base_currency='USDT'
                )
                
                logger.info("Binance broker initialized (testnet)")
            except ImportError:
                logger.warning("CCXTStore not available (ccxt not installed)")
    
    def _load_portfolio_state(self):
        """Load current portfolio state from database"""
        query = """
        SELECT 
            exchange,
            symbol,
            position_size,
            avg_entry_price,
            current_price,
            unrealized_pnl,
            total_cash,
            total_value
        FROM portfolio_state
        WHERE timestamp = (SELECT MAX(timestamp) FROM portfolio_state)
        """
        
        try:
            df = self.db.query(query)
            if not df.empty:
                for _, row in df.iterrows():
                    exchange = row['exchange'].lower()
                    if exchange in self.portfolio_state:
                        self.portfolio_state[exchange]['cash'] = row['total_cash']
                        self.portfolio_state[exchange]['total_value'] = row['total_value']
                        
                        if row['position_size'] != 0:
                            self.portfolio_state[exchange]['positions'][row['symbol']] = {
                                'size': row['position_size'],
                                'avg_price': row['avg_entry_price'],
                                'current_price': row['current_price'],
                                'pnl': row['unrealized_pnl']
                            }
                
                logger.info(f"Loaded portfolio state: {self.portfolio_state}")
        except Exception as e:
            logger.warning(f"Could not load portfolio state: {e}")
            # Initialize with default cash from config
            self.portfolio_state['alpaca']['cash'] = self.config['alpaca'].get('initial_cash', 100000)
            self.portfolio_state['binance']['cash'] = self.config['binance'].get('initial_cash', 10000)
    
    def run(self):
        """
        Main execution loop:
        1. Load active signals
        2. Validate each signal
        3. Execute valid signals
        4. Update database
        """
        logger.info("=== SignalExecutionManager.run() ===")
        
        # Load active signals
        signals = self._load_active_signals()
        
        if signals.empty:
            logger.info("No active signals to process")
            return
        
        logger.info(f"Processing {len(signals)} active signals")
        
        executed_count = 0
        rejected_count = 0
        
        for _, signal in signals.iterrows():
            try:
                # Validate signal
                is_valid, reason = self._validate_signal(signal)
                
                if not is_valid:
                    logger.info(f"Signal rejected: {signal['symbol']} - {reason}")
                    self._update_signal_status(signal['id'], 'rejected', reason)
                    rejected_count += 1
                    continue
                
                # Calculate position size
                position_size = self._calculate_position_size(signal)
                
                if position_size <= 0:
                    logger.info(f"Signal rejected: {signal['symbol']} - position size too small")
                    self._update_signal_status(signal['id'], 'rejected', 'position_size_too_small')
                    rejected_count += 1
                    continue
                
                # Execute order
                success, order_info = self._execute_signal(signal, position_size)
                
                if success:
                    logger.info(f"Signal executed: {signal['symbol']} - {order_info}")
                    self._update_signal_status(signal['id'], 'executed', json.dumps(order_info))
                    self._record_paper_trade(signal, position_size, order_info)
                    executed_count += 1
                else:
                    logger.warning(f"Signal execution failed: {signal['symbol']} - {order_info}")
                    self._update_signal_status(signal['id'], 'failed', str(order_info))
                    rejected_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing signal {signal['id']}: {e}")
                self._update_signal_status(signal['id'], 'error', str(e))
                rejected_count += 1
        
        # Update portfolio state
        self._update_portfolio_state()
        
        logger.info(f"Execution complete: {executed_count} executed, {rejected_count} rejected")
    
    def _load_active_signals(self) -> pd.DataFrame:
        """Load signals with status='active' from realtime_alerts"""
        query = """
        SELECT 
            id,
            symbol,
            signal_type,
            signal_strength,
            sentiment_score,
            confidence,
            price,
            timestamp,
            news_ids
        FROM realtime_alerts
        WHERE status = 'active'
        ORDER BY timestamp DESC
        """
        
        return self.db.query(query)
    
    def _validate_signal(self, signal: pd.Series) -> Tuple[bool, str]:
        """
        Validate trading signal against risk rules.
        
        Returns:
            (is_valid, reason)
        """
        # Determine exchange/asset type
        symbol = signal['symbol']
        is_crypto = self._is_crypto(symbol)
        exchange = 'binance' if is_crypto else 'alpaca'
        risk_cfg = self.config[exchange]['risk_settings']
        
        # Check 1: Confidence threshold
        if signal['confidence'] < risk_cfg['min_confidence']:
            return False, f"confidence_too_low_{signal['confidence']:.2f}"
        
        # Check 2: Signal age (não executar sinais muito antigos)
        signal_age = datetime.now() - pd.to_datetime(signal['timestamp'])
        max_age = timedelta(minutes=30)  # Sinais expiram em 30 minutos
        if signal_age > max_age:
            return False, f"signal_expired_{signal_age.total_seconds()/60:.0f}min"
        
        # Check 3: Trading hours (Alpaca only)
        if not is_crypto:
            trading_hours = self.config['alpaca']['trading_hours']
            if not self._is_market_open(trading_hours):
                return False, "market_closed"
        
        # Check 4: Portfolio risk limit
        current_risk = self._calculate_current_risk(exchange)
        if current_risk >= risk_cfg['max_portfolio_risk_pct']:
            return False, f"max_risk_exceeded_{current_risk:.1f}%"
        
        # Check 5: Duplicate position check
        if symbol in self.portfolio_state[exchange]['positions']:
            return False, "position_already_exists"
        
        # Check 6: Circuit breaker (daily loss limit)
        daily_pnl = self._calculate_daily_pnl(exchange)
        max_daily_loss = self.config['signal_execution']['circuit_breaker']['max_daily_loss_pct']
        initial_cash = self.portfolio_state[exchange]['total_value'] or self.portfolio_state[exchange]['cash']
        
        if daily_pnl < 0 and abs(daily_pnl / initial_cash * 100) > max_daily_loss:
            return False, f"daily_loss_limit_hit_{abs(daily_pnl/initial_cash*100):.1f}%"
        
        return True, "valid"
    
    def _is_crypto(self, symbol: str) -> bool:
        """Check if symbol is cryptocurrency"""
        crypto_pairs = self.config['binance']['trading_pairs']
        return symbol in crypto_pairs or symbol.endswith('USDT')
    
    def _is_market_open(self, trading_hours: Dict) -> bool:
        """Check if US market is open (for Alpaca)"""
        # TODO: Implementar corretamente com trading_calendars
        # Por enquanto, apenas verifica horário
        from datetime import time
        now = datetime.now()
        
        start = time(9, 30)  # 09:30 EST
        end = time(16, 0)    # 16:00 EST
        
        current_time = now.time()
        
        # Check weekday (0=Monday, 4=Friday)
        if now.weekday() > 4:
            return False
        
        return start <= current_time <= end
    
    def _calculate_current_risk(self, exchange: str) -> float:
        """Calculate current portfolio risk percentage"""
        positions = self.portfolio_state[exchange]['positions']
        total_value = self.portfolio_state[exchange]['total_value']
        
        if total_value == 0:
            return 0.0
        
        # Sum all position values
        position_value = sum(
            abs(pos['size'] * pos['current_price'])
            for pos in positions.values()
        )
        
        return (position_value / total_value) * 100
    
    def _calculate_daily_pnl(self, exchange: str) -> float:
        """Calculate today's PnL for exchange"""
        query = f"""
        SELECT SUM(pnl) as daily_pnl
        FROM paper_trades
        WHERE exchange = '{exchange}'
        AND DATE(exit_time) = DATE('now')
        AND status = 'closed'
        """
        
        result = self.db.query(query)
        if result.empty:
            return 0.0
        
        return result.iloc[0]['daily_pnl'] or 0.0
    
    def _calculate_position_size(self, signal: pd.Series) -> float:
        """
        Calculate position size using Kelly Criterion.
        
        Kelly Formula: f* = (bp - q) / b
        onde:
        - b = odds (take_profit / stop_loss)
        - p = win probability (confidence)
        - q = lose probability (1 - p)
        
        Kelly Fraction: Use apenas uma fração do Kelly (ex: 25%)
        """
        symbol = signal['symbol']
        is_crypto = self._is_crypto(symbol)
        exchange = 'binance' if is_crypto else 'alpaca'
        
        risk_cfg = self.config[exchange]['risk_settings']
        kelly_fraction = risk_cfg['kelly_fraction']
        
        # Parâmetros
        p = signal['confidence']  # Win probability
        q = 1 - p                 # Lose probability
        
        stop_loss_pct = risk_cfg['default_stop_loss_pct'] / 100
        take_profit_pct = risk_cfg['default_take_profit_pct'] / 100
        
        b = take_profit_pct / stop_loss_pct  # Odds
        
        # Kelly Criterion
        kelly_pct = (b * p - q) / b
        
        # Apply Kelly fraction
        kelly_pct = max(0, kelly_pct * kelly_fraction)
        
        # Apply max position size limit
        max_position_pct = risk_cfg['max_position_size_pct'] / 100
        kelly_pct = min(kelly_pct, max_position_pct)
        
        # Calculate position value
        available_cash = self.portfolio_state[exchange]['cash']
        position_value = available_cash * kelly_pct
        
        # Calculate position size (shares/coins)
        current_price = signal['price']
        position_size = position_value / current_price
        
        logger.info(
            f"Position size for {symbol}: "
            f"Kelly={kelly_pct*100:.2f}%, "
            f"Value=${position_value:.2f}, "
            f"Size={position_size:.6f}"
        )
        
        return position_size
    
    def _execute_signal(self, signal: pd.Series, position_size: float) -> Tuple[bool, Dict]:
        """
        Execute trading signal via appropriate broker.
        
        Returns:
            (success, order_info_dict)
        """
        symbol = signal['symbol']
        is_crypto = self._is_crypto(symbol)
        signal_type = signal['signal_type']  # 'buy' or 'sell'
        
        # Select broker
        if is_crypto:
            broker = self.ccxt_broker
            exchange = 'binance'
        else:
            broker = self.alpaca_broker
            exchange = 'alpaca'
        
        if broker is None:
            return False, {'error': f'{exchange}_broker_not_initialized'}
        
        try:
            # Create mock data for order (backtrader requires data)
            # TODO: Use proper data feed
            data = self._create_mock_data(symbol)
            
            # Submit order
            if signal_type == 'buy' or signal_type == 'long':
                order = broker.buy(
                    owner=self,
                    data=data,
                    size=position_size,
                    exectype=bt.Order.Market
                )
            else:  # sell/short
                order = broker.sell(
                    owner=self,
                    data=data,
                    size=position_size,
                    exectype=bt.Order.Market
                )
            
            # Wait for order acceptance (simple check)
            # TODO: Implement proper order tracking
            
            order_info = {
                'exchange': exchange,
                'symbol': symbol,
                'side': signal_type,
                'size': position_size,
                'price': signal['price'],
                'order_ref': order.ref,
                'timestamp': datetime.now().isoformat()
            }
            
            return True, order_info
            
        except Exception as e:
            logger.error(f"Order execution error: {e}")
            return False, {'error': str(e)}
    
    def _create_mock_data(self, symbol: str):
        """Create mock data object for backtrader (temporary)"""
        # TODO: Replace with proper data feed
        class MockData:
            _name = symbol
        
        return MockData()
    
    def _update_signal_status(self, signal_id: str, status: str, details: str):
        """Update realtime_alerts status"""
        update_query = f"""
        UPDATE realtime_alerts
        SET status = '{status}',
            execution_details = '{details}',
            execution_time = '{datetime.now().isoformat()}'
        WHERE id = '{signal_id}'
        """
        
        self.db.execute(update_query)
    
    def _record_paper_trade(self, signal: pd.Series, position_size: float, order_info: Dict):
        """Record trade in paper_trades table"""
        is_crypto = self._is_crypto(signal['symbol'])
        exchange = 'binance' if is_crypto else 'alpaca'
        risk_cfg = self.config[exchange]['risk_settings']
        
        # Calculate stop-loss and take-profit prices
        entry_price = signal['price']
        
        if signal['signal_type'] == 'buy':
            stop_loss = entry_price * (1 - risk_cfg['default_stop_loss_pct']/100)
            take_profit = entry_price * (1 + risk_cfg['default_take_profit_pct']/100)
        else:  # sell/short
            stop_loss = entry_price * (1 + risk_cfg['default_stop_loss_pct']/100)
            take_profit = entry_price * (1 - risk_cfg['default_take_profit_pct']/100)
        
        trade_data = {
            'id': f"{exchange}_{signal['symbol']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'exchange': exchange,
            'symbol': signal['symbol'],
            'side': signal['signal_type'],
            'entry_price': entry_price,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now().isoformat(),
            'status': 'open',
            'sentiment_score': signal['sentiment_score'],
            'confidence': signal['confidence'],
            'signal_id': signal['id']
        }
        
        # Insert into database
        df = pd.DataFrame([trade_data])
        self.db.save_dataframe(df, 'paper_trades', mode='append')
        
        logger.info(f"Recorded paper trade: {trade_data['id']}")
    
    def _update_portfolio_state(self):
        """Update portfolio_state table with current positions"""
        timestamp = datetime.now().isoformat()
        
        for exchange in ['alpaca', 'binance']:
            state = self.portfolio_state[exchange]
            
            # Record overall portfolio
            portfolio_row = {
                'timestamp': timestamp,
                'exchange': exchange,
                'symbol': 'TOTAL',
                'position_size': 0,
                'avg_entry_price': 0,
                'current_price': 0,
                'unrealized_pnl': 0,
                'total_cash': state['cash'],
                'total_value': state['total_value']
            }
            
            rows = [portfolio_row]
            
            # Record each position
            for symbol, pos in state['positions'].items():
                position_row = {
                    'timestamp': timestamp,
                    'exchange': exchange,
                    'symbol': symbol,
                    'position_size': pos['size'],
                    'avg_entry_price': pos['avg_price'],
                    'current_price': pos['current_price'],
                    'unrealized_pnl': pos['pnl'],
                    'total_cash': state['cash'],
                    'total_value': state['total_value']
                }
                rows.append(position_row)
            
            df = pd.DataFrame(rows)
            self.db.save_dataframe(df, 'portfolio_state', mode='append')
        
        logger.info("Portfolio state updated")


def main():
    """Test execution"""
    manager = SignalExecutionManager()
    manager.run()


if __name__ == '__main__':
    main()
