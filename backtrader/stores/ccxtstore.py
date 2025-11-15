#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2025 Daniel Rodriguez / Wagner Montes
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import collections
from datetime import datetime, timedelta
import time as _time
import threading
import json

import backtrader as bt
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import queue, with_metaclass
from backtrader.utils import AutoDict

# CCXT import
try:
    import ccxt
except ImportError:
    ccxt = None


class CCXTRequestError(Exception):
    """CCXT request error"""
    def __init__(self, message='Request Error'):
        self.message = message
        super().__init__(self.message)


class CCXTStreamError(Exception):
    """CCXT streaming error"""
    def __init__(self, message='Streaming Error'):
        self.message = message
        super().__init__(self.message)


class CCXTNetworkError(Exception):
    """CCXT network error"""
    def __init__(self, message='Network Error'):
        self.message = message
        super().__init__(self.message)


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class CCXTStore(with_metaclass(MetaSingleton, object)):
    '''Singleton class wrapping CCXT exchange connections.

    This store works with any exchange supported by CCXT library.

    Params:

      - ``exchange`` (default: ``'binance'``): Exchange name (must be supported by CCXT)
        Examples: 'binance', 'coinbase', 'kraken', 'bitfinex', 'ftx', etc.

      - ``api_key`` (default: ``''``): Exchange API key

      - ``api_secret`` (default: ``''``): Exchange API secret

      - ``password`` (default: ``''``): Exchange password (required for some exchanges like Coinbase)

      - ``sandbox`` (default: ``True``): Use sandbox/testnet mode (True) or live (False)

      - ``enableRateLimit`` (default: ``True``): Enable built-in rate limiter

      - ``notifyall`` (default: ``False``): If False only ``error`` messages 
        will be sent to the ``notify_store`` methods of ``Cerebro`` and ``Strategy``.
        If True, each and every message received from exchange will be notified

      - ``_debug`` (default: ``False``): Print all messages to standard output

      - ``timeout`` (default: ``30000``): Timeout for API requests in milliseconds

      - ``options`` (default: ``{}``): Additional options passed to CCXT exchange constructor
        Example: {'defaultType': 'spot'} or {'defaultType': 'future'}

      - ``reconnect`` (default: ``3``): Number of attempts to try to reconnect 
        after the 1st connection attempt fails. Set it to a ``-1`` value to 
        keep on reconnecting forever

      - ``config`` (default: ``{}``): Complete config dict for CCXT exchange
        Overrides individual parameters if provided
    '''

    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    params = (
        ('exchange', 'binance'),
        ('api_key', ''),
        ('api_secret', ''),
        ('password', ''),
        ('sandbox', True),
        ('enableRateLimit', True),
        ('notifyall', False),
        ('_debug', False),
        ('timeout', 30000),
        ('options', {}),
        ('reconnect', 3),
        ('config', {}),
    )

    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self):
        super(CCXTStore, self).__init__()

        if ccxt is None:
            raise ImportError('ccxt not installed. Install with: pip install ccxt')

        self._lock_notif = threading.Lock()  # sync access to notif queue

        self._env = None  # reference to cerebro for general notifications
        self.broker = None  # broker instance
        self.datas = list()  # datas that have registered over start
        
        self.notifs = queue.Queue()  # store notifications for cerebro

        # CCXT exchange instance
        self._exchange = None
        
        # Account info
        self._cash = {}  # cash by currency
        self._value = 0.0
        self._balance = None
        
        # Positions tracking (for futures)
        self.positions = collections.defaultdict(lambda: 0)
        
        # Orders tracking
        self.orders = {}  # order_id -> order object
        self.orderbyid = {}  # exchange order id -> bt order
        
        # Markets info
        self._markets = {}
        
        # Streaming
        self._stream_thread = None
        self._stream_running = False

    def start(self, data=None, broker=None):
        '''Start the store (connect to exchange)'''
        if not self._exchange:
            # Get exchange class
            exchange_id = self.p.exchange.lower()
            
            if not hasattr(ccxt, exchange_id):
                raise ValueError(f'Exchange {exchange_id} not supported by CCXT')
            
            exchange_class = getattr(ccxt, exchange_id)
            
            # Build config
            if self.p.config:
                # Use provided config
                config = self.p.config.copy()
            else:
                # Build config from parameters
                config = {
                    'apiKey': self.p.api_key,
                    'secret': self.p.api_secret,
                    'enableRateLimit': self.p.enableRateLimit,
                    'timeout': self.p.timeout,
                }
                
                if self.p.password:
                    config['password'] = self.p.password
                
                if self.p.options:
                    config['options'] = self.p.options
            
            try:
                # Create exchange instance
                self._exchange = exchange_class(config)
                
                # Enable sandbox mode if requested
                if self.p.sandbox:
                    if hasattr(self._exchange, 'set_sandbox_mode'):
                        self._exchange.set_sandbox_mode(True)
                        if self.p._debug:
                            print(f'{exchange_id} sandbox mode enabled')
                    else:
                        if self.p._debug:
                            print(f'{exchange_id} does not support sandbox mode')
                
                # Load markets
                self._markets = self._exchange.load_markets()
                
                # Get initial balance
                self._update_balance()
                
                if self.p._debug:
                    print(f'CCXT {exchange_id} connected: Sandbox={self.p.sandbox}, Markets={len(self._markets)}')
                    print(f'Balance: {self._cash}')
                
            except Exception as e:
                self.put_notification(f'Failed to connect to {exchange_id}: {e}')
                raise CCXTNetworkError(f'Connection failed: {e}')

        # Register data or broker
        if data is not None:
            self._env = data._env
            self.datas.append(data)
            
            if self.broker is not None:
                if hasattr(self.broker, 'data_started'):
                    self.broker.data_started(data)
                    
        elif broker is not None:
            self.broker = broker

    def stop(self):
        '''Stop the store'''
        if self._stream_running:
            self._stream_running = False
            if self._stream_thread:
                self._stream_thread.join()
        
        # Close exchange connection
        if self._exchange and hasattr(self._exchange, 'close'):
            self._exchange.close()

    def put_notification(self, msg, *args, **kwargs):
        '''Add notification to queue'''
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark
        return [x for x in iter(self.notifs.popleft, None)]

    def _update_balance(self):
        '''Update account balance from exchange'''
        try:
            self._balance = self._exchange.fetch_balance()
            
            # Extract free/used/total
            self._cash = self._balance.get('free', {})
            
            # Calculate total value (simplified - would need prices for accurate calculation)
            self._value = sum(self._cash.values())
            
        except Exception as e:
            if self.p._debug:
                print(f'Error updating balance: {e}')

    def get_cash(self, currency='USDT'):
        '''Returns the current cash (free balance) for a currency'''
        try:
            self._update_balance()
            return self._cash.get(currency, 0.0)
        except Exception as e:
            if self.p._debug:
                print(f'Error getting cash: {e}')
            return 0.0

    def get_value(self):
        '''Returns the current portfolio value'''
        try:
            self._update_balance()
            return self._value
        except Exception as e:
            if self.p._debug:
                print(f'Error getting value: {e}')
            return self._value

    def get_balance(self):
        '''Returns complete balance info'''
        try:
            self._update_balance()
            return self._balance
        except Exception as e:
            if self.p._debug:
                print(f'Error getting balance: {e}')
            return self._balance

    def get_positions(self):
        '''Returns all current positions (for futures/derivatives)'''
        try:
            if hasattr(self._exchange, 'fetch_positions'):
                positions = self._exchange.fetch_positions()
                self.positions.clear()
                for pos in positions:
                    symbol = pos.get('symbol')
                    contracts = float(pos.get('contracts', 0))
                    side = pos.get('side')  # 'long' or 'short'
                    if side == 'short':
                        contracts = -contracts
                    self.positions[symbol] = contracts
                return self.positions
            else:
                # Spot trading doesn't have positions
                return {}
        except Exception as e:
            if self.p._debug:
                print(f'Error getting positions: {e}')
            return self.positions

    def getposition(self, symbol):
        '''Returns the position for a given symbol (futures only)'''
        try:
            if hasattr(self._exchange, 'fetch_positions'):
                positions = self._exchange.fetch_positions([symbol])
                if positions:
                    pos = positions[0]
                    contracts = float(pos.get('contracts', 0))
                    side = pos.get('side')
                    if side == 'short':
                        contracts = -contracts
                    return contracts
            return 0.0
        except Exception as e:
            if self.p._debug:
                print(f'Error getting position for {symbol}: {e}')
            return 0.0

    def create_order(self, symbol, order_type, side, amount, price=None, params={}):
        '''Create an order on the exchange
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            order_type: 'market', 'limit', 'stop_market', 'stop_limit'
            side: 'buy' or 'sell'
            amount: Amount to trade
            price: Limit price (for limit orders)
            params: Additional parameters (stopPrice, etc.)
            
        Returns:
            Order object from exchange or None if failed
        '''
        try:
            # Map order types
            if order_type == 'stop_market':
                # For stop market orders
                params['stopPrice'] = params.get('stopPrice', price)
                order = self._exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side=side,
                    amount=amount,
                    params=params
                )
            elif order_type == 'stop_limit':
                # For stop limit orders
                params['stopPrice'] = params.get('stopPrice')
                order = self._exchange.create_order(
                    symbol=symbol,
                    type='stop_limit',
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
            else:
                # Market or limit order
                order = self._exchange.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
            
            if self.p._debug:
                print(f'Order created: {order["id"]} {side} {amount} {symbol} @ {order_type}')
            
            return order
            
        except Exception as e:
            if self.p._debug:
                print(f'Error creating order: {e}')
            self.put_notification(f'Order creation failed: {e}')
            return None

    def cancel_order(self, order_id, symbol=None):
        '''Cancel an order by ID'''
        try:
            result = self._exchange.cancel_order(order_id, symbol)
            if self.p._debug:
                print(f'Order cancelled: {order_id}')
            return True
        except Exception as e:
            if self.p._debug:
                print(f'Error cancelling order {order_id}: {e}')
            return False

    def get_order(self, order_id, symbol=None):
        '''Get order status by ID'''
        try:
            order = self._exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            if self.p._debug:
                print(f'Error getting order {order_id}: {e}')
            return None

    def get_orders(self, symbol=None, since=None, limit=None):
        '''Get orders (open or all)
        
        Args:
            symbol: Trading pair filter
            since: Timestamp in ms
            limit: Max number of orders
        '''
        try:
            orders = self._exchange.fetch_orders(symbol, since, limit)
            return orders
        except Exception as e:
            if self.p._debug:
                print(f'Error getting orders: {e}')
            return []

    def get_open_orders(self, symbol=None):
        '''Get open orders'''
        try:
            orders = self._exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            if self.p._debug:
                print(f'Error getting open orders: {e}')
            return []

    def get_markets(self):
        '''Get all available markets'''
        return self._markets

    def get_market(self, symbol):
        '''Get market info for a symbol'''
        return self._markets.get(symbol)

    def fetch_ohlcv(self, symbol, timeframe='1m', since=None, limit=None):
        '''Fetch OHLCV data
        
        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: '1m', '5m', '15m', '1h', '4h', '1d', '1w', etc.
            since: Timestamp in ms
            limit: Number of candles
            
        Returns:
            List of OHLCV candles
        '''
        try:
            ohlcv = self._exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            return ohlcv
        except Exception as e:
            if self.p._debug:
                print(f'Error fetching OHLCV: {e}')
            return []

    def fetch_ticker(self, symbol):
        '''Fetch current ticker (price, volume, etc.)'''
        try:
            ticker = self._exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            if self.p._debug:
                print(f'Error fetching ticker: {e}')
            return {}

    def get_timeframe_ms(self, timeframe):
        '''Convert timeframe string to milliseconds'''
        if hasattr(self._exchange, 'parse_timeframe'):
            return self._exchange.parse_timeframe(timeframe) * 1000
        
        # Fallback manual conversion
        timeframe_map = {
            '1m': 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000,
        }
        return timeframe_map.get(timeframe, 60 * 1000)

    def streaming_events(self, tmout=None):
        '''Check for streaming events (placeholder for WebSocket support)'''
        # TODO: Implement WebSocket streaming using ccxt.pro
        pass
