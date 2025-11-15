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
import threading
import time

import backtrader as bt
from backtrader.broker import BrokerBase
from backtrader.order import Order, BuyOrder, SellOrder
from backtrader.position import Position
from backtrader.utils.py3 import queue, with_metaclass
from backtrader.comminfo import CommInfoBase

from backtrader.stores import ccxtstore


class MetaCCXTBroker(BrokerBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaCCXTBroker, cls).__init__(name, bases, dct)
        ccxtstore.CCXTStore.BrokerCls = cls


class CCXTBroker(with_metaclass(MetaCCXTBroker, BrokerBase)):
    '''Broker implementation for CCXT (Universal Crypto Exchange Broker).

    This broker works with any exchange supported by CCXT library.

    Params:

      - ``use_positions`` (default: ``True``): When connecting to the broker
        provider use the existing positions to kickstart the broker.
        Set to ``False`` during instantiation to disregard any existing position

      - ``base_currency`` (default: ``'USDT'``): Base currency for cash calculations
        Common options: 'USDT', 'USD', 'BTC', 'ETH'

      - ``maker_fee`` (default: ``0.001``): Maker fee (0.1% = 0.001)

      - ``taker_fee`` (default: ``0.001``): Taker fee (0.1% = 0.001)

    Notes:

      - This broker supports both spot and futures trading depending on exchange capabilities

      - Fees are exchange-specific and should be configured according to your exchange tier

      - Position management for futures trading is fully supported
    '''
    
    params = (
        ('use_positions', True),
        ('base_currency', 'USDT'),
        ('maker_fee', 0.001),  # 0.1%
        ('taker_fee', 0.001),  # 0.1%
    )

    def __init__(self, **kwargs):
        super(CCXTBroker, self).__init__()

        self.ccxt = ccxtstore.CCXTStore(**kwargs)
        
        self.startingcash = self.cash = 0.0
        self.startingvalue = self.value = 0.0
        
        self._lock_orders = threading.Lock()
        self.orderbyid = {}  # exchange order id -> bt order
        self.orders = collections.OrderedDict()  # bt order -> exchange order
        
        self.notifs = queue.Queue()
        self.positions = collections.defaultdict(Position)

        self._oref = 0  # order reference counter

    def start(self):
        super(CCXTBroker, self).start()
        self.ccxt.start(broker=self)
        
        if self.ccxt._exchange:
            self.startingcash = self.cash = self.ccxt.get_cash(self.p.base_currency)
            self.startingvalue = self.value = self.ccxt.get_value()
            
            # Load existing positions if requested (futures only)
            if self.p.use_positions:
                self._load_positions()
        else:
            self.startingcash = self.cash = 0.0
            self.startingvalue = self.value = 0.0

    def _load_positions(self):
        '''Load existing positions from exchange (futures only)'''
        try:
            positions = self.ccxt.get_positions()
            for symbol, size in positions.items():
                if size != 0:
                    # Create a position for tracking
                    self.positions[symbol] = Position(size=size, price=0.0)
        except Exception as e:
            if self.ccxt.p._debug:
                print(f'Error loading positions: {e}')

    def stop(self):
        super(CCXTBroker, self).stop()
        self.ccxt.stop()

    def getcash(self):
        '''Returns the current cash (buying power) in base currency'''
        self.cash = self.ccxt.get_cash(self.p.base_currency)
        return self.cash

    def getvalue(self, datas=None):
        '''Returns the current portfolio value'''
        self.value = self.ccxt.get_value()
        return self.value

    def get_notification(self):
        '''Get next notification from queue'''
        try:
            return self.notifs.get(False)
        except queue.Empty:
            return None

    def notify(self, order):
        '''Add order notification to queue'''
        self.notifs.put(order)

    def getposition(self, data, clone=True):
        '''Returns the position for a given data (asset)'''
        symbol = self._format_symbol(data._name)
        
        # Get position from exchange (futures) or calculate from balance (spot)
        if hasattr(self.ccxt._exchange, 'fetch_positions'):
            # Futures - get position from exchange
            pos_size = self.ccxt.getposition(symbol)
        else:
            # Spot - calculate from balance
            # Extract base asset from pair (e.g., BTC from BTC/USDT)
            base_asset = symbol.split('/')[0]
            balance = self.ccxt.get_balance()
            pos_size = balance.get('free', {}).get(base_asset, 0.0)
        
        # Update internal position tracking
        if symbol not in self.positions:
            self.positions[symbol] = Position(size=pos_size, price=0.0)
        else:
            self.positions[symbol].size = pos_size
        
        if clone:
            return self.positions[symbol].clone()
        
        return self.positions[symbol]

    def _format_symbol(self, symbol):
        '''Format symbol to CCXT standard (e.g., BTCUSDT -> BTC/USDT)'''
        # Check if already formatted
        if '/' in symbol:
            return symbol
        
        # Try to split common patterns
        # e.g., BTCUSDT, ETHUSDT, etc.
        common_quote = ['USDT', 'USD', 'BTC', 'ETH', 'BNB', 'BUSD']
        for quote in common_quote:
            if symbol.endswith(quote):
                base = symbol[:-len(quote)]
                return f'{base}/{quote}'
        
        # If can't split, return as is (might fail on exchange)
        return symbol

    def orderstatus(self, order):
        '''Returns the status of an order'''
        try:
            ccxt_order = self.orders.get(order, None)
            if ccxt_order:
                # Get updated order status from exchange
                symbol = self._format_symbol(order.data._name)
                updated_order = self.ccxt.get_order(ccxt_order['id'], symbol)
                if updated_order:
                    return self._process_order_status(updated_order, order)
            
            return order.status
        except Exception as e:
            if self.ccxt.p._debug:
                print(f'Error getting order status: {e}')
            return order.status

    def _process_order_status(self, ccxt_order, bt_order):
        '''Process CCXT order status and update backtrader order'''
        status_map = {
            'open': Order.Submitted,
            'closed': Order.Completed,
            'canceled': Order.Cancelled,
            'cancelled': Order.Cancelled,
            'expired': Order.Expired,
            'rejected': Order.Rejected,
        }
        
        status = status_map.get(ccxt_order.get('status'), Order.Submitted)
        
        # Update execution info if filled
        if ccxt_order.get('filled', 0) > 0:
            bt_order.execute(
                dt=bt.date2num(time.time()),
                size=float(ccxt_order['filled']),
                price=float(ccxt_order.get('average', ccxt_order.get('price', 0))),
                closed=float(ccxt_order['filled']),
                value=float(ccxt_order.get('cost', 0)),
                comm=float(ccxt_order.get('fee', {}).get('cost', 0)),
                pnl=0.0
            )
        
        return status

    def submit(self, order):
        '''Submit an order to exchange'''
        order.submit(self)
        
        self._oref += 1
        order.ref = self._oref
        
        # Determine order parameters
        symbol = self._format_symbol(order.data._name)
        amount = abs(order.created.size)
        side = 'buy' if order.isbuy() else 'sell'
        
        # Determine order type
        if order.exectype == Order.Market:
            order_type = 'market'
            price = None
            params = {}
        elif order.exectype == Order.Limit:
            order_type = 'limit'
            price = order.created.price
            params = {}
        elif order.exectype == Order.Stop:
            order_type = 'stop_market'
            price = order.created.price
            params = {'stopPrice': order.created.price}
        elif order.exectype == Order.StopLimit:
            order_type = 'stop_limit'
            price = order.created.pricelimit
            params = {'stopPrice': order.created.price}
        else:
            # Unsupported order type
            order.reject()
            self.notify(order)
            return order
        
        # Submit order to exchange
        try:
            ccxt_order = self.ccxt.create_order(
                symbol=symbol,
                order_type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            if ccxt_order:
                # Store mapping
                with self._lock_orders:
                    self.orders[order] = ccxt_order
                    self.orderbyid[ccxt_order['id']] = order
                
                # Set order as accepted
                order.accept()
                self.notify(order)
            else:
                # Order submission failed
                order.reject()
                self.notify(order)
                
        except Exception as e:
            if self.ccxt.p._debug:
                print(f'Error submitting order: {e}')
            order.reject()
            self.notify(order)
        
        return order

    def cancel(self, order):
        '''Cancel an order'''
        if order not in self.orders:
            return
        
        ccxt_order = self.orders[order]
        symbol = self._format_symbol(order.data._name)
        
        try:
            success = self.ccxt.cancel_order(ccxt_order['id'], symbol)
            
            if success:
                order.cancel()
                self.notify(order)
            
        except Exception as e:
            if self.ccxt.p._debug:
                print(f'Error cancelling order: {e}')

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            parent=None, transmit=True,
            **kwargs):
        '''Create a buy order'''
        order = BuyOrder(owner=owner, data=data, size=size, price=price,
                        pricelimit=plimit, exectype=exectype, valid=valid,
                        tradeid=tradeid, oco=oco,
                        trailamount=trailamount, trailpercent=trailpercent,
                        parent=parent, transmit=transmit)
        
        order.addinfo(**kwargs)
        return self.submit(order)

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             parent=None, transmit=True,
             **kwargs):
        '''Create a sell order'''
        order = SellOrder(owner=owner, data=data, size=size, price=price,
                         pricelimit=plimit, exectype=exectype, valid=valid,
                         tradeid=tradeid, oco=oco,
                         trailamount=trailamount, trailpercent=trailpercent,
                         parent=parent, transmit=transmit)
        
        order.addinfo(**kwargs)
        return self.submit(order)

    def getcommissioninfo(self, data):
        '''Returns commission info for the exchange'''
        # Use configurable fees
        comm = CommInfoBase(
            commission=self.p.taker_fee,  # Use taker fee as default
            mult=1.0,
            margin=None,
            commtype=CommInfoBase.COMM_PERC,  # Percentage commission
            stocklike=False,
            percabs=True
        )
        return comm


BrokerCCXT = CCXTBroker
