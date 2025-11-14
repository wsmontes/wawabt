"""
RSI Mean Reversion Strategy
Buy when RSI is oversold, sell when RSI is overbought
"""
import backtrader as bt


class RSIMeanReversionStrategy(bt.Strategy):
    """
    RSI Mean Reversion Strategy
    
    Parameters:
        rsi_period: Period for RSI calculation (default: 14)
        rsi_oversold: RSI level considered oversold (default: 30)
        rsi_overbought: RSI level considered overbought (default: 70)
        printlog: Whether to print trade logs (default: True)
    """
    
    params = (
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        ('printlog', True),
    )
    
    def log(self, txt, dt=None):
        """Logging function"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
    
    def __init__(self):
        """Initialize indicators"""
        self.dataclose = self.datas[0].close
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # RSI indicator
        self.rsi = bt.indicators.RSI(
            self.datas[0],
            period=self.params.rsi_period
        )
    
    def notify_order(self, order):
        """Called when order status changes"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
            else:
                self.log(
                    f'SELL EXECUTED, Price: {order.executed.price:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        
        self.order = None
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if not trade.isclosed:
            return
        
        self.log(f'OPERATION PROFIT, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}')
    
    def next(self):
        """Called for each bar"""
        self.log(f'Close: {self.dataclose[0]:.2f}, RSI: {self.rsi[0]:.2f}')
        
        if self.order:
            return
        
        if not self.position:
            # Not in market - look for buy signal (oversold)
            if self.rsi[0] < self.params.rsi_oversold:
                self.log(f'BUY CREATE, RSI Oversold: {self.rsi[0]:.2f}')
                self.order = self.buy()
        
        else:
            # In market - look for sell signal (overbought)
            if self.rsi[0] > self.params.rsi_overbought:
                self.log(f'SELL CREATE, RSI Overbought: {self.rsi[0]:.2f}')
                self.order = self.sell()
    
    def stop(self):
        """Called at the end of the backtest"""
        self.log(
            f'(RSI Period={self.params.rsi_period}, '
            f'Oversold={self.params.rsi_oversold}, '
            f'Overbought={self.params.rsi_overbought}) '
            f'Ending Value: {self.broker.getvalue():.2f}'
        )


if __name__ == '__main__':
    import sys
    from datetime import datetime, timedelta
    sys.path.insert(0, '..')
    
    from engines.bt_data import create_data_feed
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(RSIMeanReversionStrategy)
    
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
