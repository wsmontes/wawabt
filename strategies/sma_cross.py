"""
Simple Moving Average Crossover Strategy
Buy when fast SMA crosses above slow SMA, sell when it crosses below
"""
import backtrader as bt


class SMACrossStrategy(bt.Strategy):
    """
    Simple Moving Average Crossover Strategy
    
    Parameters:
        fast_period: Period for fast moving average (default: 10)
        slow_period: Period for slow moving average (default: 30)
        printlog: Whether to print trade logs (default: True)
    """
    
    params = (
        ('fast_period', 10),
        ('slow_period', 30),
        ('printlog', True),
    )
    
    def log(self, txt, dt=None):
        """Logging function"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
    
    def __init__(self):
        """Initialize indicators"""
        # Keep reference to the close price
        self.dataclose = self.datas[0].close
        
        # Track pending orders
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # Add moving averages
        self.fast_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], 
            period=self.params.fast_period
        )
        self.slow_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], 
            period=self.params.slow_period
        )
        
        # Crossover signal
        self.crossover = bt.indicators.CrossOver(self.fast_sma, self.slow_sma)
    
    def notify_order(self, order):
        """Called when order status changes"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - no action required
            return
        
        # Check if order has been completed
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:  # Sell
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
            
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        # Reset order
        self.order = None
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if not trade.isclosed:
            return
        
        self.log(f'OPERATION PROFIT, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}')
    
    def next(self):
        """Called for each bar"""
        # Log current close
        self.log(f'Close: {self.dataclose[0]:.2f}')
        
        # Check if we have an order pending
        if self.order:
            return
        
        # Check if we are in the market
        if not self.position:
            # Not in market - look for buy signal
            if self.crossover > 0:  # Fast SMA crossed above slow SMA
                self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
                self.order = self.buy()
        
        else:
            # In market - look for sell signal
            if self.crossover < 0:  # Fast SMA crossed below slow SMA
                self.log(f'SELL CREATE, {self.dataclose[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        """Called at the end of the backtest"""
        self.log(
            f'(Fast={self.params.fast_period}, Slow={self.params.slow_period}) '
            f'Ending Value: {self.broker.getvalue():.2f}',
            dt=self.datas[0].datetime.date(0)
        )


if __name__ == '__main__':
    """
    This strategy can be run directly or via bt_run.py
    
    Direct run:
        python strategies/sma_cross.py
    
    Via bt_run.py:
        python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL
    """
    import sys
    from datetime import datetime, timedelta
    sys.path.insert(0, '..')
    
    from engines.bt_data import create_data_feed
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(SMACrossStrategy)
    
    # Add data
    data = create_data_feed(
        'AAPL',
        fromdate=datetime.now() - timedelta(days=365),
        todate=datetime.now()
    )
    
    if data:
        cerebro.adddata(data)
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')
        cerebro.run()
        print(f'Final Portfolio Value: {cerebro.broker.getvalue():.2f}')
    else:
        print("Failed to load data")
