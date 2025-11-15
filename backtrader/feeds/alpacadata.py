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

from datetime import datetime, timedelta

import backtrader as bt
from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num, num2date
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                   with_metaclass)
from backtrader.metabase import MetaParams
from backtrader.stores import alpacastore


class MetaAlpacaData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaAlpacaData, cls).__init__(name, bases, dct)

        # Register with the store
        alpacastore.AlpacaStore.DataCls = cls


class AlpacaData(with_metaclass(MetaAlpacaData, DataBase)):
    '''Alpaca Data Feed.

    Params:

      - ``historical`` (default: ``False``)
        If set to ``True`` the data feed will stop after doing the first
        download of data.

        The standard data feed parameters ``fromdate`` and ``todate`` will be
        used as reference.

        The data feed will make multiple requests if the requested duration is
        larger than the one allowed by Alpaca servers.

      - ``backfill_start`` (default: ``True``)
        Perform backfilling at the start. The maximum possible historical data
        will be fetched in a single request.

      - ``backfill`` (default: ``True``)
        Perform backfilling after a disconnection/reconnection cycle. The gap
        duration will be used to download the smallest possible amount of data

      - ``backfill_from`` (default: ``None``)
        An additional data source can be passed to do an initial layer of
        backfilling. Once the data source is depleted and if requested,
        backfilling from Alpaca will take place. This is ideally meant to
        backfill from already stored sources like a file on disk, but not
        limited to.

      - ``bidask`` (default: ``True``)
        If ``True``, then the historical/backfilling requests will request
        bid/ask prices from the server

        If ``False``, then the historical/backfilling requests will only
        request the OHLCV prices

      - ``useask`` (default: ``False``)
        If ``True`` the *ask* part of the *bidask* prices will be used instead
        of the default use of *bid*

      - ``reconnect`` (default: ``True``)
        Reconnect when network connection is down

      - ``reconnections`` (default: ``-1``)
        Number of times to attempt reconnections: ``-1`` means forever

      - ``reconntimeout`` (default: ``5.0``)
        Time in seconds to wait in between reconnection attemps

      - ``data_feed`` (default: ``'iex'``)
        Data feed to use: 'iex', 'sip', 'otc'

    The Alpaca API key and secret must be provided in one of the following ways:

      - Passing ``api_key`` and ``api_secret`` as kwargs to the data feed

      - Using the environment variables ``APCA_API_KEY_ID`` and ``APCA_API_SECRET_KEY``

      - Via the AlpacaStore parameters

    '''

    params = (
        ('historical', False),
        ('backfill_start', True),
        ('backfill', True),
        ('backfill_from', None),
        ('bidask', True),
        ('useask', False),
        ('reconnect', True),
        ('reconnections', -1),
        ('reconntimeout', 5.0),
        ('data_feed', 'iex'),  # 'iex', 'sip', 'otc'
    )

    _store = alpacastore.AlpacaStore

    # States for the Finite State Machine in _load
    _ST_FROM, _ST_START, _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(5)

    def _timeoffset(self):
        # Effective way to overcome the non-notification?
        return self.p.sessionstart is not None

    def islive(self):
        '''Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated'''
        return not self.p.historical

    def __init__(self, **kwargs):
        self.alpaca = self._store(**kwargs)
        self._data = None  # data in queue for current iteration
        self._last = None  # datetime of last received bar

    def setenvironment(self, env):
        '''Receives an environment (cerebro) and passes it over to the store it
        belongs to'''
        super(AlpacaData, self).setenvironment(env)
        env.addstore(self.alpaca)

    def start(self):
        '''Starts the Alpaca connection and gets the real contract and
        contractdetails if it exists'''
        super(AlpacaData, self).start()

        # Kickstart store and get queue to wait on
        self.alpaca.start(data=self)

        # check if data is historical
        if not self.p.historical:
            self._state = self._ST_LIVE
            if self.p.backfill_start:
                self._start_backfill()
        else:
            self._state = self._ST_START
            self._start_historical()

        self._reconns = 0

    def _start_backfill(self):
        '''Start backfilling data'''
        dtend = None
        if self.todate is not None:
            dtend = num2date(self.todate)

        dtbegin = None
        if self.fromdate is not None:
            dtbegin = num2date(self.fromdate)
        
        if dtbegin is None:
            # Default to 1 day ago if no from date
            dtbegin = datetime.utcnow() - timedelta(days=1)

        self._state = self._ST_HISTORBACK
        self._load_historical(dtbegin, dtend)

    def _start_historical(self):
        '''Start loading historical data'''
        dtend = None
        if self.todate is not None:
            dtend = num2date(self.todate)
        else:
            dtend = datetime.utcnow()

        dtbegin = None
        if self.fromdate is not None:
            dtbegin = num2date(self.fromdate)
        else:
            # Default to 1 year ago
            dtbegin = dtend - timedelta(days=365)

        self._load_historical(dtbegin, dtend)
        self._state = self._ST_HISTORBACK

    def _load_historical(self, dtbegin, dtend):
        '''Load historical data from Alpaca'''
        try:
            # Get timeframe
            timeframe = self._timeframe_to_alpaca()
            
            # Import Alpaca types
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            
            # Create request
            request_params = StockBarsRequest(
                symbol_or_symbols=self.p.dataname,
                timeframe=timeframe,
                start=dtbegin,
                end=dtend,
                feed=self.p.data_feed
            )
            
            # Get bars from Alpaca
            bars = self.alpaca._data_client.get_stock_bars(request_params)
            
            # Convert to list for processing
            if hasattr(bars, 'df'):
                # If it's a BarsSet with dataframe
                df = bars.df
                if not df.empty:
                    self._data_queue = []
                    for idx, row in df.iterrows():
                        bar = {
                            'time': idx,
                            'open': row['open'],
                            'high': row['high'],
                            'low': row['low'],
                            'close': row['close'],
                            'volume': row['volume']
                        }
                        self._data_queue.append(bar)
            else:
                # If it's a dict with symbol keys
                symbol_bars = bars.get(self.p.dataname, [])
                self._data_queue = []
                for bar in symbol_bars:
                    bar_dict = {
                        'time': bar.timestamp,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume)
                    }
                    self._data_queue.append(bar_dict)
                    
        except Exception as e:
            if self.alpaca.p._debug:
                print(f'Error loading historical data: {e}')
            self._data_queue = []

    def _timeframe_to_alpaca(self):
        '''Convert backtrader timeframe to Alpaca TimeFrame'''
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        
        if self._timeframe == TimeFrame.Minutes:
            if self._compression == 1:
                return TimeFrame(1, TimeFrameUnit.Minute)
            elif self._compression == 5:
                return TimeFrame(5, TimeFrameUnit.Minute)
            elif self._compression == 15:
                return TimeFrame(15, TimeFrameUnit.Minute)
            else:
                return TimeFrame(self._compression, TimeFrameUnit.Minute)
        
        elif self._timeframe == TimeFrame.Days:
            return TimeFrame(1, TimeFrameUnit.Day)
        
        elif self._timeframe == TimeFrame.Weeks:
            return TimeFrame(1, TimeFrameUnit.Week)
        
        elif self._timeframe == TimeFrame.Months:
            return TimeFrame(1, TimeFrameUnit.Month)
        
        # Default to daily
        return TimeFrame(1, TimeFrameUnit.Day)

    def stop(self):
        '''Stops and tells the store to stop'''
        super(AlpacaData, self).stop()
        self.alpaca.stop()

    def haslivedata(self):
        '''Returns ``True`` if there is data available'''
        return bool(self._data_queue) if hasattr(self, '_data_queue') else False

    def _load(self):
        '''Load the next bar'''
        if self._state == self._ST_OVER:
            return False

        # For historical data
        if self._state == self._ST_HISTORBACK:
            if hasattr(self, '_data_queue') and self._data_queue:
                bar = self._data_queue.pop(0)
                
                # Fill the line with bar data
                self.lines.datetime[0] = date2num(bar['time'])
                self.lines.open[0] = bar['open']
                self.lines.high[0] = bar['high']
                self.lines.low[0] = bar['low']
                self.lines.close[0] = bar['close']
                self.lines.volume[0] = bar['volume']
                self.lines.openinterest[0] = 0
                
                return True
            else:
                # No more historical data
                if self.p.historical:
                    self._state = self._ST_OVER
                    return False
                else:
                    # Switch to live mode
                    self._state = self._ST_LIVE
                    return self._load()  # Try to load live data

        # For live data (placeholder - would need WebSocket implementation)
        elif self._state == self._ST_LIVE:
            # TODO: Implement WebSocket streaming for live data
            # For now, return False to indicate no live data available
            return False

        return False


DataAlpaca = AlpacaData
