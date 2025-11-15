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

from backtrader.stores import alpacastore


class MetaAlpacaBroker(BrokerBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaAlpacaBroker, cls).__init__(name, bases, dct)
        alpacastore.AlpacaStore.BrokerCls = cls


class AlpacaBroker(with_metaclass(MetaAlpacaBroker, BrokerBase)):
    '''Broker implementation for Alpaca.

    This class maps the orders/positions from Alpaca to the
    internal API of ``backtrader``.

    Params:

      - ``use_positions`` (default: ``True``): When connecting to the broker
        provider use the existing positions to kickstart the broker.

        Set to ``False`` during instantiation to disregard any existing
        position

    Notes:

      - Position

        If there is an open position for an asset at the beginning of
        operations or orders given by other means change a position, the trades
        calculated in the ``Strategy`` in cerebro will not reflect the reality.

        To avoid this, this broker would have to do its own position
        management which would also allow tradeid with multiple ids (profit and
        loss would also be calculated locally), but could be considered to be
        defeating the purpose of working with a live broker
    '''
    
    params = (
        ('use_positions', True),
    )

    def __init__(self, **kwargs):
        super(AlpacaBroker, self).__init__()

        self.alpaca = alpacastore.AlpacaStore(**kwargs)
        
        self.startingcash = self.cash = 0.0
        self.startingvalue = self.value = 0.0
        
        self._lock_orders = threading.Lock()
        self.orderbyid = {}  # broker order id -> bt order
        self.orders = collections.OrderedDict()  # bt order -> broker order
        
        self.notifs = queue.Queue()
        self.positions = collections.defaultdict(Position)

        self._oref = 0  # order reference counter

    def start(self):
        super(AlpacaBroker, self).start()
        self.alpaca.start(broker=self)
        
        if self.alpaca._trading_client:
            self.startingcash = self.cash = self.alpaca.get_cash()
            self.startingvalue = self.value = self.alpaca.get_value()
            
            # Load existing positions if requested
            if self.p.use_positions:
                self._load_positions()
        else:
            self.startingcash = self.cash = 0.0
            self.startingvalue = self.value = 0.0

    def _load_positions(self):
        '''Load existing positions from Alpaca'''
        try:
            positions = self.alpaca.get_positions()
            for symbol, qty in positions.items():
                if qty != 0:
                    # Create a position for tracking
                    # Note: This is simplified - in production you'd want more details
                    self.positions[symbol] = Position(size=qty, price=0.0)
        except Exception as e:
            if self.alpaca.p._debug:
                print(f'Error loading positions: {e}')

    def stop(self):
        super(AlpacaBroker, self).stop()
        self.alpaca.stop()

    def getcash(self):
        '''Returns the current cash (buying power)'''
        self.cash = self.alpaca.get_cash()
        return self.cash

    def getvalue(self, datas=None):
        '''Returns the current portfolio value (equity)'''
        self.value = self.alpaca.get_value()
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
        symbol = data._name
        
        # Get position from Alpaca
        pos_size = self.alpaca.getposition(symbol)
        
        # Update internal position tracking
        if symbol not in self.positions:
            self.positions[symbol] = Position(size=pos_size, price=0.0)
        else:
            self.positions[symbol].size = pos_size
        
        if clone:
            return self.positions[symbol].clone()
        
        return self.positions[symbol]

    def orderstatus(self, order):
        '''Returns the status of an order'''
        try:
            alpaca_order = self.orders.get(order, None)
            if alpaca_order:
                # Get updated order status from Alpaca
                updated_order = self.alpaca.get_order(alpaca_order.id)
                if updated_order:
                    return self._process_order_status(updated_order, order)
            
            return order.status
        except Exception as e:
            if self.alpaca.p._debug:
                print(f'Error getting order status: {e}')
            return order.status

    def _process_order_status(self, alpaca_order, bt_order):
        '''Process Alpaca order status and update backtrader order'''
        status_map = {
            'new': Order.Submitted,
            'partially_filled': Order.Partial,
            'filled': Order.Completed,
            'canceled': Order.Cancelled,
            'expired': Order.Expired,
            'replaced': Order.Cancelled,
            'pending_cancel': Order.Submitted,
            'pending_replace': Order.Submitted,
            'accepted': Order.Accepted,
            'pending_new': Order.Submitted,
            'accepted_for_bidding': Order.Accepted,
            'stopped': Order.Cancelled,
            'rejected': Order.Rejected,
            'suspended': Order.Cancelled,
        }
        
        status = status_map.get(alpaca_order.status, Order.Submitted)
        
        # Update execution info
        if alpaca_order.filled_qty:
            bt_order.execute(
                dt=alpaca_order.filled_at if hasattr(alpaca_order, 'filled_at') else bt.date2num(time.time()),
                size=float(alpaca_order.filled_qty),
                price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else 0.0,
                closed=float(alpaca_order.filled_qty),
                value=float(alpaca_order.filled_qty) * float(alpaca_order.filled_avg_price or 0.0),
                comm=0.0,  # Alpaca charges no commission
                pnl=0.0
            )
        
        return status

    def submit(self, order):
        '''Submit an order to Alpaca'''
        order.submit(self)
        
        self._oref += 1
        order.ref = self._oref
        
        # Determine order parameters
        symbol = order.data._name
        size = abs(order.created.size)
        is_buy = order.isbuy()
        
        # Determine order type
        if order.exectype == Order.Market:
            order_type = 'market'
            price = None
            stop_price = None
        elif order.exectype == Order.Limit:
            order_type = 'limit'
            price = order.created.price
            stop_price = None
        elif order.exectype == Order.Stop:
            order_type = 'stop'
            price = None
            stop_price = order.created.price
        elif order.exectype == Order.StopLimit:
            order_type = 'stop_limit'
            price = order.created.pricelimit
            stop_price = order.created.price
        else:
            # Unsupported order type
            order.reject()
            self.notify(order)
            return order
        
        # Determine time in force
        if order.valid is None:
            time_in_force = 'gtc'  # Good til cancelled
        elif order.valid == 0:
            time_in_force = 'day'
        else:
            time_in_force = 'gtc'
        
        # Submit order to Alpaca
        try:
            alpaca_order = self.alpaca.submit_order(
                symbol=symbol,
                size=int(size),
                is_buy=is_buy,
                order_type=order_type,
                price=price,
                stop_price=stop_price,
                time_in_force=time_in_force
            )
            
            if alpaca_order:
                # Store mapping
                with self._lock_orders:
                    self.orders[order] = alpaca_order
                    self.orderbyid[alpaca_order.id] = order
                
                # Set order as accepted
                order.accept()
                self.notify(order)
            else:
                # Order submission failed
                order.reject()
                self.notify(order)
                
        except Exception as e:
            if self.alpaca.p._debug:
                print(f'Error submitting order: {e}')
            order.reject()
            self.notify(order)
        
        return order

    def cancel(self, order):
        '''Cancel an order'''
        if order not in self.orders:
            return
        
        alpaca_order = self.orders[order]
        
        try:
            success = self.alpaca.cancel_order(alpaca_order.id)
            
            if success:
                order.cancel()
                self.notify(order)
            
        except Exception as e:
            if self.alpaca.p._debug:
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
        '''Returns commission info for Alpaca (zero commission)'''
        # Alpaca charges no commission for stock trading
        comm = CommInfoBase(
            commission=0.0,
            mult=1.0,
            margin=None,
            commtype=CommInfoBase.COMM_FIXED,
            stocklike=True,
            percabs=False
        )
        return comm


BrokerAlpaca = AlpacaBroker
