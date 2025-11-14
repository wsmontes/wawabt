"""
Engines package for data management and connectivity
"""

from .database import DatabaseEngine
from .smart_db import SmartDatabaseManager
from .connector import ConnectorEngine
from .rss import RSSEngine
from .datasets import DatasetsEngine
from .bt_data import AutoFetchData, create_data_feed, create_multiple_feeds
from .analyzer_helper import AnalyzerHelper, AnalyzerPresets
from .commission_helper import CommissionHelper, setup_commission
from .cerebro_runner import CerebroRunner, quick_backtest

__all__ = [
    # Core engines
    'DatabaseEngine', 
    'SmartDatabaseManager',
    'ConnectorEngine', 
    'RSSEngine', 
    'DatasetsEngine',
    
    # Backtrader integration
    'AutoFetchData',
    'create_data_feed',
    'create_multiple_feeds',
    
    # Helpers
    'AnalyzerHelper',
    'AnalyzerPresets',
    'CommissionHelper',
    'setup_commission',
    'CerebroRunner',
    'quick_backtest',
]
