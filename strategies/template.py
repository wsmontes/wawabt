"""
Strategy Template
Copy this file and modify it to create your own strategy
"""
import backtrader as bt


class MyStrategy(bt.Strategy):
    """
    [DESCRIPTION]
    Describe your strategy here
    
    Parameters:
        param1: Description (default: value)
        param2: Description (default: value)
        printlog: Whether to print trade logs (default: True)
    """
    
    params = (
        ('param1', 10),
        ('param2', 20),
        ('printlog', True),
    )
    
    def log(self, txt, dt=None):
        """Logging function for strategy output"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
    
    def __init__(self):
        """
        Initialize your indicators and variables here
        Called once at the start
        """
        # Keep reference to close price
        self.dataclose = self.datas[0].close
        
        # Track orders
        self.order = None
        self.buyprice = None
        self.buycomm = None
        
        # Add your indicators here
        # Example: self.sma = bt.indicators.SimpleMovingAverage(self.datas[0], period=20)
        # Example: self.rsi = bt.indicators.RSI(self.datas[0], period=14)
        # Example: self.macd = bt.indicators.MACD(self.datas[0])
        
        pass
    
    def notify_order(self, order):
        """
        Called when order status changes
        Handles order execution notifications
        """
        if order.status in [order.Submitted, order.Accepted]:
            # Order submitted/accepted - nothing to do
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
        
        # Reset order variable
        self.order = None
    
    def notify_trade(self, trade):
        """
        Called when a trade is closed
        """
        if not trade.isclosed:
            return
        
        self.log(
            f'OPERATION PROFIT, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}'
        )
    
    def next(self):
        """
        Called for each bar/candle
        This is where your trading logic goes
        """
        # Log current close price
        self.log(f'Close: {self.dataclose[0]:.2f}')
        
        # Check if we have a pending order
        if self.order:
            return
        
        # Check if we are in the market
        if not self.position:
            # Not in market - check for BUY signal
            # TODO: Add your buy logic here
            # Example:
            # if self.sma[0] > self.dataclose[0]:
            #     self.log(f'BUY CREATE, {self.dataclose[0]:.2f}')
            #     self.order = self.buy()
            pass
        
        else:
            # In market - check for SELL signal
            # TODO: Add your sell logic here
            # Example:
            # if self.sma[0] < self.dataclose[0]:
            #     self.log(f'SELL CREATE, {self.dataclose[0]:.2f}')
            #     self.order = self.sell()
            pass
    
    def stop(self):
        """
        Called at the end of the backtest
        Print final statistics here
        """
        self.log(
            f'(Params: {self.params.param1}, {self.params.param2}) '
            f'Ending Value: {self.broker.getvalue():.2f}'
        )


if __name__ == '__main__':
    """
    Test the strategy directly
    
    Run with:
        python strategies/template.py
    
    Or use bt_run.py:
        python bt_run.py --strategy strategies/template.py --symbols AAPL
    """
    import sys
    from datetime import datetime, timedelta
    sys.path.insert(0, '..')
    
    from engines.bt_data import create_data_feed
    
    # Create Cerebro engine
    cerebro = bt.Cerebro()
    
    # Add strategy
    cerebro.addstrategy(MyStrategy)
    
    # Load data
    data = create_data_feed(
        'AAPL',  # Change this to your symbol
        fromdate=datetime.now() - timedelta(days=365),
        todate=datetime.now()
    )
    
    if data:
        cerebro.adddata(data)
        
        # Set broker parameters
        cerebro.broker.setcash(10000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        # Add analyzers
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        
        # Run backtest
        print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
        results = cerebro.run()
        print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
        
        # Print analyzer results
        strat = results[0]
        
        sharpe = strat.analyzers.sharpe.get_analysis()
        if 'sharperatio' in sharpe and sharpe['sharperatio'] is not None:
            print(f'Sharpe Ratio: {sharpe["sharperatio"]:.2f}')
        
        dd = strat.analyzers.drawdown.get_analysis()
        if 'max' in dd and 'drawdown' in dd['max']:
            print(f'Max Drawdown: {dd["max"]["drawdown"]:.2f}%')
        
        # Optionally plot results
        # cerebro.plot(style='candlestick')
    else:
        print("Failed to load data")
