"""
Multi-Symbol Portfolio Strategy
Trades multiple symbols simultaneously with equal allocation
Uses simple momentum to rotate positions
"""
import backtrader as bt


class MultiSymbolPortfolioStrategy(bt.Strategy):
    """
    Multi-Symbol Portfolio Strategy with Momentum
    
    Parameters:
        momentum_period: Lookback period for momentum (default: 20)
        rebalance_days: Days between rebalancing (default: 30)
        top_n: Number of top momentum stocks to hold (default: 3)
        printlog: Whether to print trade logs (default: True)
    """
    
    params = (
        ('momentum_period', 20),
        ('rebalance_days', 30),
        ('top_n', 3),
        ('printlog', True),
    )
    
    def log(self, txt, dt=None):
        """Logging function"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'[{dt.isoformat()}] {txt}')
    
    def __init__(self):
        """Initialize indicators for each data feed"""
        self.orders = {}
        self.days_since_rebalance = 0
        
        # Calculate momentum for each symbol
        self.momentum = {}
        for i, d in enumerate(self.datas):
            # Momentum = (current price / price N days ago) - 1
            self.momentum[d] = bt.indicators.ROC(d.close, period=self.params.momentum_period)
    
    def notify_order(self, order):
        """Called when order status changes"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'BUY EXECUTED [{order.data._name}], '
                    f'Price: {order.executed.price:.2f}, '
                    f'Size: {order.executed.size:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
            else:
                self.log(
                    f'SELL EXECUTED [{order.data._name}], '
                    f'Price: {order.executed.price:.2f}, '
                    f'Size: {order.executed.size:.2f}, '
                    f'Cost: {order.executed.value:.2f}, '
                    f'Comm: {order.executed.comm:.2f}'
                )
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'Order Canceled/Margin/Rejected [{order.data._name}]')
        
        # Remove from pending orders
        if order.data in self.orders:
            del self.orders[order.data]
    
    def notify_trade(self, trade):
        """Called when a trade is closed"""
        if not trade.isclosed:
            return
        
        self.log(
            f'TRADE CLOSED [{trade.data._name}], '
            f'Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}'
        )
    
    def next(self):
        """Called for each bar"""
        # Increment rebalance counter
        self.days_since_rebalance += 1
        
        # Check if we have pending orders
        if self.orders:
            return
        
        # Rebalance portfolio every N days
        if self.days_since_rebalance >= self.params.rebalance_days:
            self.rebalance_portfolio()
            self.days_since_rebalance = 0
    
    def rebalance_portfolio(self):
        """Rebalance portfolio based on momentum"""
        self.log('=' * 60)
        self.log('REBALANCING PORTFOLIO')
        
        # Calculate momentum scores for all symbols
        momentum_scores = []
        for d in self.datas:
            if len(d) > self.params.momentum_period:
                score = self.momentum[d][0]
                momentum_scores.append((d, score))
        
        if not momentum_scores:
            self.log('Not enough data for rebalancing')
            return
        
        # Sort by momentum (highest first)
        momentum_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Log momentum scores
        self.log('Momentum Scores:')
        for d, score in momentum_scores:
            self.log(f'  {d._name}: {score:.2f}%')
        
        # Select top N symbols
        top_symbols = [d for d, _ in momentum_scores[:self.params.top_n]]
        
        self.log(f'\nTop {self.params.top_n} symbols: {[d._name for d in top_symbols]}')
        
        # Close positions not in top N
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0 and d not in top_symbols:
                self.log(f'Closing position in {d._name}')
                self.orders[d] = self.close(data=d)
        
        # Calculate target allocation for each top symbol
        cash = self.broker.getcash()
        total_value = self.broker.getvalue()
        target_value_per_symbol = total_value / self.params.top_n
        
        self.log(f'\nPortfolio Value: ${total_value:.2f}')
        self.log(f'Available Cash: ${cash:.2f}')
        self.log(f'Target per Symbol: ${target_value_per_symbol:.2f}')
        
        # Open/adjust positions in top N
        for d in top_symbols:
            pos = self.getposition(d)
            current_value = pos.size * d.close[0]
            target_shares = int(target_value_per_symbol / d.close[0])
            diff_shares = target_shares - pos.size
            
            if abs(diff_shares) > 0:
                if diff_shares > 0:
                    self.log(f'Buying {diff_shares} shares of {d._name} @ ${d.close[0]:.2f}')
                    self.orders[d] = self.buy(data=d, size=diff_shares)
                else:
                    self.log(f'Selling {abs(diff_shares)} shares of {d._name} @ ${d.close[0]:.2f}')
                    self.orders[d] = self.sell(data=d, size=abs(diff_shares))
        
        self.log('=' * 60)
    
    def stop(self):
        """Called at the end of the backtest"""
        self.log(f'\nFinal Portfolio Value: ${self.broker.getvalue():.2f}')
        
        # Log final positions
        self.log('\nFinal Positions:')
        for d in self.datas:
            pos = self.getposition(d)
            if pos.size > 0:
                value = pos.size * d.close[0]
                self.log(f'  {d._name}: {pos.size:.0f} shares @ ${d.close[0]:.2f} = ${value:.2f}')


if __name__ == '__main__':
    import sys
    from datetime import datetime, timedelta
    sys.path.insert(0, '..')
    
    from engines.bt_data import create_multiple_feeds
    
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MultiSymbolPortfolioStrategy)
    
    # Add multiple symbols
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
    feeds = create_multiple_feeds(
        symbols,
        fromdate=datetime.now() - timedelta(days=365),
        todate=datetime.now()
    )
    
    if feeds:
        for symbol, feed in feeds.items():
            cerebro.adddata(feed, name=symbol)
        
        cerebro.broker.setcash(100000.0)
        cerebro.broker.setcommission(commission=0.001)
        
        print(f'Starting Portfolio Value: ${cerebro.broker.getvalue():.2f}')
        cerebro.run()
        print(f'Final Portfolio Value: ${cerebro.broker.getvalue():.2f}')
    else:
        print("Failed to load data")
