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

# Alpaca imports
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.requests import (
        MarketOrderRequest, LimitOrderRequest, StopOrderRequest, 
        StopLimitOrderRequest, GetOrdersRequest
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderClass
    from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
except ImportError:
    TradingClient = None
    StockHistoricalDataClient = None


class AlpacaRequestError(Exception):
    """Alpaca request error"""
    def __init__(self, message='Request Error'):
        self.message = message
        super().__init__(self.message)


class AlpacaStreamError(Exception):
    """Alpaca streaming error"""
    def __init__(self, message='Streaming Error'):
        self.message = message
        super().__init__(self.message)


class AlpacaNetworkError(Exception):
    """Alpaca network error"""
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


class AlpacaStore(with_metaclass(MetaSingleton, object)):
    '''Singleton class wrapping Alpaca API connections.

    The parameters can also be specified in the classes which use this store,
    like ``AlpacaData`` and ``AlpacaBroker``

    Params:

      - ``api_key`` (default: ``''``): Alpaca API key

      - ``api_secret`` (default: ``''``): Alpaca API secret

      - ``paper`` (default: ``True``): Use paper trading (True) or live (False)

      - ``account`` (default: ``None``): Account to use (for multiple accounts)

      - ``notifyall`` (default: ``False``): If False only ``error`` messages 
        will be sent to the ``notify_store`` methods of ``Cerebro`` and ``Strategy``.
        If True, each and every message received from Alpaca will be notified

      - ``_debug`` (default: ``False``): Print all messages received from 
        Alpaca to standard output

      - ``data_feed`` (default: ``'iex'``): Data feed to use ('iex', 'sip', 'otc')

      - ``reconnect`` (default: ``3``): Number of attempts to try to reconnect 
        after the 1st connection attempt fails. Set it to a ``-1`` value to 
        keep on reconnecting forever

      - ``timeout`` (default: ``10.0``): Timeout for API requests in seconds
    '''

    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    params = (
        ('api_key', ''),
        ('api_secret', ''),
        ('paper', True),
        ('account', None),
        ('notifyall', False),
        ('_debug', False),
        ('data_feed', 'iex'),  # 'iex', 'sip', 'otc'
        ('reconnect', 3),
        ('timeout', 10.0),
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
        super(AlpacaStore, self).__init__()

        if TradingClient is None:
            raise ImportError('alpaca-py not installed. Install with: pip install alpaca-py')

        self._lock_notif = threading.Lock()  # sync access to notif queue

        self._env = None  # reference to cerebro for general notifications
        self.broker = None  # broker instance
        self.datas = list()  # datas that have registered over start
        
        self.notifs = queue.Queue()  # store notifications for cerebro

        # Alpaca clients
        self._trading_client = None
        self._data_client = None
        
        # Account info
        self._cash = 0.0
        self._value = 0.0
        self._account = None
        
        # Positions tracking
        self.positions = collections.defaultdict(lambda: 0)
        
        # Orders tracking
        self.orders = {}  # order_id -> order object
        self.orderbyid = {}  # broker order id -> bt order
        
        # Streaming
        self._stream_thread = None
        self._stream_running = False

    def start(self, data=None, broker=None):
        '''Start the store (connect to Alpaca)'''
        if not self._trading_client:
            # Initialize Alpaca clients
            base_url = 'https://paper-api.alpaca.markets' if self.p.paper else 'https://api.alpaca.markets'
            
            try:
                self._trading_client = TradingClient(
                    api_key=self.p.api_key,
                    secret_key=self.p.api_secret,
                    paper=self.p.paper
                )
                
                self._data_client = StockHistoricalDataClient(
                    api_key=self.p.api_key,
                    secret_key=self.p.api_secret
                )
                
                # Get initial account info
                self._account = self._trading_client.get_account()
                self._cash = float(self._account.cash)
                self._value = float(self._account.equity)
                
                if self.p._debug:
                    print(f'Alpaca connected: Paper={self.p.paper}, Cash=${self._cash:.2f}, Equity=${self._value:.2f}')
                
            except Exception as e:
                self.put_notification(f'Failed to connect to Alpaca: {e}')
                raise AlpacaNetworkError(f'Connection failed: {e}')

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

    def put_notification(self, msg, *args, **kwargs):
        '''Add notification to queue'''
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark
        return [x for x in iter(self.notifs.popleft, None)]

    def get_cash(self):
        '''Returns the current cash (buy power) in the account'''
        try:
            account = self._trading_client.get_account()
            self._cash = float(account.cash)
            self._value = float(account.equity)
            return self._cash
        except Exception as e:
            if self.p._debug:
                print(f'Error getting cash: {e}')
            return self._cash

    def get_value(self):
        '''Returns the current portfolio value (equity) in the account'''
        try:
            account = self._trading_client.get_account()
            self._value = float(account.equity)
            self._cash = float(account.cash)
            return self._value
        except Exception as e:
            if self.p._debug:
                print(f'Error getting value: {e}')
            return self._value

    def get_positions(self):
        '''Returns all current positions'''
        try:
            positions = self._trading_client.get_all_positions()
            self.positions.clear()
            for pos in positions:
                self.positions[pos.symbol] = float(pos.qty)
            return self.positions
        except Exception as e:
            if self.p._debug:
                print(f'Error getting positions: {e}')
            return self.positions

    def getposition(self, symbol):
        '''Returns the position for a given symbol'''
        try:
            position = self._trading_client.get_open_position(symbol)
            return float(position.qty) if position else 0.0
        except Exception as e:
            if self.p._debug:
                print(f'Error getting position for {symbol}: {e}')
            return 0.0

    def submit_order(self, symbol, size, is_buy, order_type='market', 
                     price=None, stop_price=None, time_in_force='day'):
        '''Submit an order to Alpaca
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            size: Number of shares (positive integer)
            is_buy: True for buy, False for sell
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: 'day', 'gtc', 'opg', 'cls', 'ioc', 'fok'
            
        Returns:
            Order object from Alpaca or None if failed
        '''
        try:
            side = OrderSide.BUY if is_buy else OrderSide.SELL
            
            # Map time_in_force
            tif_map = {
                'day': TimeInForce.DAY,
                'gtc': TimeInForce.GTC,
                'opg': TimeInForce.OPG,
                'cls': TimeInForce.CLS,
                'ioc': TimeInForce.IOC,
                'fok': TimeInForce.FOK,
            }
            tif = tif_map.get(time_in_force.lower(), TimeInForce.DAY)
            
            # Create order request based on type
            if order_type == 'market':
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=size,
                    side=side,
                    time_in_force=tif
                )
            elif order_type == 'limit':
                if price is None:
                    raise ValueError('Limit price required for limit orders')
                order_request = LimitOrderRequest(
                    symbol=symbol,
                    qty=size,
                    side=side,
                    time_in_force=tif,
                    limit_price=price
                )
            elif order_type == 'stop':
                if stop_price is None:
                    raise ValueError('Stop price required for stop orders')
                order_request = StopOrderRequest(
                    symbol=symbol,
                    qty=size,
                    side=side,
                    time_in_force=tif,
                    stop_price=stop_price
                )
            elif order_type == 'stop_limit':
                if price is None or stop_price is None:
                    raise ValueError('Both limit and stop price required for stop-limit orders')
                order_request = StopLimitOrderRequest(
                    symbol=symbol,
                    qty=size,
                    side=side,
                    time_in_force=tif,
                    limit_price=price,
                    stop_price=stop_price
                )
            else:
                raise ValueError(f'Unknown order type: {order_type}')
            
            # Submit order
            order = self._trading_client.submit_order(order_request)
            
            if self.p._debug:
                print(f'Order submitted: {order.id} {side} {size} {symbol} @ {order_type}')
            
            return order
            
        except Exception as e:
            if self.p._debug:
                print(f'Error submitting order: {e}')
            self.put_notification(f'Order submission failed: {e}')
            return None

    def cancel_order(self, order_id):
        '''Cancel an order by ID'''
        try:
            self._trading_client.cancel_order_by_id(order_id)
            if self.p._debug:
                print(f'Order cancelled: {order_id}')
            return True
        except Exception as e:
            if self.p._debug:
                print(f'Error cancelling order {order_id}: {e}')
            return False

    def get_order(self, order_id):
        '''Get order status by ID'''
        try:
            order = self._trading_client.get_order_by_id(order_id)
            return order
        except Exception as e:
            if self.p._debug:
                print(f'Error getting order {order_id}: {e}')
            return None

    def get_orders(self, status='all'):
        '''Get orders by status
        
        Args:
            status: 'all', 'open', 'closed'
        '''
        try:
            request = GetOrdersRequest(status=status)
            orders = self._trading_client.get_orders(filter=request)
            return orders
        except Exception as e:
            if self.p._debug:
                print(f'Error getting orders: {e}')
            return []

    def streaming_events(self, tmout=None):
        '''Check for streaming events (placeholder for future WebSocket support)'''
        # TODO: Implement WebSocket streaming for real-time data
        pass

    def candles_to_df(self, candles):
        '''Convert Alpaca bars to pandas DataFrame'''
        import pandas as pd
        
        data = []
        for bar in candles:
            data.append({
                'timestamp': bar.timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': int(bar.volume)
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
        
        return df

    def get_granularity(self, timeframe):
        '''Convert backtrader timeframe to Alpaca TimeFrame'''
        # Map timeframe strings to Alpaca TimeFrame
        # Examples: '1Min', '5Min', '15Min', '1Hour', '1Day'
        
        if hasattr(timeframe, 'lower'):
            tf_lower = timeframe.lower()
            
            # Minutes
            if 'min' in tf_lower:
                minutes = int(tf_lower.replace('min', ''))
                return TimeFrame(minutes, TimeFrameUnit.Minute)
            
            # Hours
            elif 'hour' in tf_lower or 'h' in tf_lower:
                hours = int(tf_lower.replace('hour', '').replace('h', ''))
                return TimeFrame(hours, TimeFrameUnit.Hour)
            
            # Days
            elif 'day' in tf_lower or 'd' in tf_lower:
                return TimeFrame(1, TimeFrameUnit.Day)
            
            # Weeks
            elif 'week' in tf_lower or 'w' in tf_lower:
                return TimeFrame(1, TimeFrameUnit.Week)
            
            # Months
            elif 'month' in tf_lower or 'm' in tf_lower:
                return TimeFrame(1, TimeFrameUnit.Month)
        
        # Default to 1 day
        return TimeFrame(1, TimeFrameUnit.Day)
