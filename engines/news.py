"""
News Engine - Centralized news management with strict validation
Handles news from multiple sources (RSS, APIs, Connector) with timestamp validation
Ensures data integrity for sentiment analysis
"""
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import hashlib
import json

try:
    from .smart_db import SmartDatabaseManager
except ImportError:
    SmartDatabaseManager = None

try:
    from .rss import RSSEngine
except ImportError:
    RSSEngine = None

try:
    from .connector import ConnectorEngine
except ImportError:
    ConnectorEngine = None


class NewsEngine:
    """
    Centralized news engine with strict validation
    - Validates timestamps (must be timezone-aware UTC)
    - Deduplicates news items
    - Standardizes schema across sources
    - Integrates with SmartDatabaseManager
    """
    
    # Required fields for news items
    REQUIRED_FIELDS = ['timestamp', 'title', 'source']
    
    # Optional fields with defaults
    OPTIONAL_FIELDS = {
        'description': '',
        'link': '',
        'category': 'general',
        'author': '',
        'image_url': '',
        'tags': '',
        'sentiment': None,  # Can be added by sentiment analysis
        'cryptos_mentioned': '',
        'tickers_mentioned': ''
    }
    
    def __init__(self, 
                 db_config_path: str = "config/database.json",
                 use_database: bool = True,
                 strict_validation: bool = True):
        """
        Initialize News Engine
        
        Args:
            db_config_path: Path to database configuration
            use_database: Whether to use database integration
            strict_validation: If True, reject invalid data; if False, fix and warn
        """
        self.db = None
        self.use_database = use_database
        self.strict_validation = strict_validation
        
        if use_database and SmartDatabaseManager:
            try:
                self.db = SmartDatabaseManager(db_config_path)
                print("[NewsEngine] Database integration enabled")
            except Exception as e:
                print(f"[NewsEngine] Database initialization failed: {e}")
                self.db = None
    
    def validate_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """
        Validate and normalize timestamp to timezone-aware UTC
        
        Args:
            timestamp: Input timestamp (datetime, string, or unix timestamp)
        
        Returns:
            Validated datetime in UTC or None if invalid
        """
        if timestamp is None:
            return None
        
        try:
            # If already datetime
            if isinstance(timestamp, datetime):
                # Check if timezone-aware
                if timestamp.tzinfo is None:
                    if self.strict_validation:
                        print(f"[NewsEngine] WARNING: Naive datetime detected: {timestamp}")
                        return None
                    else:
                        # Assume UTC
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                        print(f"[NewsEngine] Fixed naive datetime, assumed UTC: {timestamp}")
                
                # Convert to UTC
                return timestamp.astimezone(timezone.utc)
            
            # If string, parse ISO format
            elif isinstance(timestamp, str):
                # Try ISO format
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except ValueError:
                    pass
                
                # Try parsing common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S']:
                    try:
                        dt = datetime.strptime(timestamp, fmt)
                        dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except ValueError:
                        continue
            
            # If unix timestamp (int or float)
            elif isinstance(timestamp, (int, float)):
                # Check if seconds or milliseconds
                if timestamp > 1e10:  # Likely milliseconds
                    timestamp = timestamp / 1000
                
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            
            print(f"[NewsEngine] ERROR: Cannot parse timestamp: {timestamp} (type: {type(timestamp)})")
            return None
            
        except Exception as e:
            print(f"[NewsEngine] ERROR: Timestamp validation failed: {e}")
            return None
    
    def validate_news_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate a single news item
        
        Args:
            item: News item dictionary
        
        Returns:
            Validated and normalized news item or None if invalid
        """
        if not isinstance(item, dict):
            print(f"[NewsEngine] ERROR: News item must be dict, got {type(item)}")
            return None
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in item or item[field] is None:
                print(f"[NewsEngine] ERROR: Missing required field '{field}' in news item")
                if self.strict_validation:
                    return None
        
        # Validate timestamp
        validated_timestamp = self.validate_timestamp(item.get('timestamp'))
        if validated_timestamp is None:
            print(f"[NewsEngine] ERROR: Invalid timestamp in news item: {item.get('title', 'Unknown')[:50]}")
            if self.strict_validation:
                return None
            else:
                return None  # Can't proceed without valid timestamp
        
        # Create validated item with all fields
        validated_item = {
            'timestamp': validated_timestamp,
            'title': str(item.get('title', 'Untitled'))[:500],
            'source': str(item.get('source', 'unknown'))[:100]
        }
        
        # Add optional fields
        for field, default in self.OPTIONAL_FIELDS.items():
            value = item.get(field, default)
            if field in ['description', 'link', 'author']:
                validated_item[field] = str(value)[:1000] if value else default
            else:
                validated_item[field] = value if value else default
        
        # Generate content hash for deduplication
        hash_content = f"{validated_item['title']}|{validated_item['link']}|{validated_item['timestamp'].isoformat()}"
        validated_item['content_hash'] = hashlib.md5(hash_content.encode()).hexdigest()
        
        return validated_item
    
    def validate_news_batch(self, news_items: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Validate a batch of news items
        
        Args:
            news_items: List of news item dictionaries
        
        Returns:
            DataFrame with validated news items
        """
        if not news_items:
            print("[NewsEngine] WARNING: Empty news batch")
            return pd.DataFrame()
        
        print(f"[NewsEngine] Validating {len(news_items)} news items...")
        
        validated_items = []
        invalid_count = 0
        
        for item in news_items:
            validated = self.validate_news_item(item)
            if validated:
                validated_items.append(validated)
            else:
                invalid_count += 1
        
        print(f"[NewsEngine] ✓ Validated: {len(validated_items)} items")
        if invalid_count > 0:
            print(f"[NewsEngine] ⚠ Rejected: {invalid_count} invalid items")
        
        if not validated_items:
            return pd.DataFrame()
        
        df = pd.DataFrame(validated_items)
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Deduplicate by content hash
        original_len = len(df)
        df = df.drop_duplicates(subset=['content_hash'], keep='last')
        if len(df) < original_len:
            print(f"[NewsEngine] ℹ Removed {original_len - len(df)} duplicate items")
        
        return df
    
    def store_news(self, news_items: Union[List[Dict[str, Any]], pd.DataFrame], 
                   source: str = 'unknown') -> bool:
        """
        Validate and store news items to database
        
        Args:
            news_items: List of news dicts or DataFrame
            source: Source identifier for storage
        
        Returns:
            True if successful, False otherwise
        """
        # Convert to DataFrame if needed
        if isinstance(news_items, list):
            df = self.validate_news_batch(news_items)
        elif isinstance(news_items, pd.DataFrame):
            # Validate each row
            items_list = news_items.to_dict('records')
            df = self.validate_news_batch(items_list)
        else:
            print(f"[NewsEngine] ERROR: Invalid input type: {type(news_items)}")
            return False
        
        if df.empty:
            print("[NewsEngine] No valid news items to store")
            return False
        
        # Store to database
        if self.db:
            try:
                self.db.store_news_data(df, source=source)
                print(f"[NewsEngine] ✓ Stored {len(df)} news items to database (source: {source})")
                return True
            except Exception as e:
                print(f"[NewsEngine] ERROR: Database storage failed: {e}")
                return False
        else:
            print("[NewsEngine] WARNING: No database connection, news not stored")
            return False
    
    def query_news(self, 
                   source: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   category: Optional[str] = None,
                   crypto: Optional[str] = None) -> pd.DataFrame:
        """
        Query news from database with filters
        
        Args:
            source: Filter by source
            start_date: Start date (timezone-aware)
            end_date: End date (timezone-aware)
            category: Filter by category
            crypto: Filter by mentioned cryptocurrency
        
        Returns:
            DataFrame with matching news items
        """
        if not self.db:
            print("[NewsEngine] ERROR: No database connection")
            return pd.DataFrame()
        
        try:
            # Query from database
            df = self.db.query_news_data(
                source=source,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None
            )
            
            # Additional filtering
            if not df.empty:
                if category:
                    df = df[df['category'] == category]
                
                if crypto:
                    df = df[df['cryptos_mentioned'].str.contains(crypto, na=False, case=False)]
            
            print(f"[NewsEngine] ✓ Retrieved {len(df)} news items")
            return df
            
        except Exception as e:
            print(f"[NewsEngine] ERROR: Query failed: {e}")
            return pd.DataFrame()
    
    def get_recent_news(self, 
                       limit: int = 100,
                       sources: Optional[List[str]] = None,
                       category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent news articles from database
        
        Args:
            limit: Maximum number of articles to return
            sources: List of sources to filter by
            category: Category to filter by
        
        Returns:
            List of news articles as dictionaries
        """
        if not self.db:
            print("[NewsEngine] ERROR: No database connection")
            return []
        
        try:
            # Query from database
            df = self.db.query_news_data(
                source=sources[0] if sources and len(sources) == 1 else None
            )
            
            # Additional filtering
            if not df.empty:
                if sources and len(sources) > 1:
                    df = df[df['source'].isin(sources)]
                
                if category:
                    df = df[df['category'] == category]
                
                # Sort by date and limit
                df = df.sort_values('published_date', ascending=False).head(limit)
            
            # Convert to list of dicts
            return df.to_dict('records')
            
        except Exception as e:
            print(f"[NewsEngine] ERROR: Query failed: {e}")
            return []
    
    def integrate_rss_engine(self, rss_config_path: str = "config/rss_sources.json") -> bool:
        """
        Fetch news from RSS Engine and store with validation
        
        Args:
            rss_config_path: Path to RSS configuration
        
        Returns:
            True if successful
        """
        if RSSEngine is None:
            print("[NewsEngine] ERROR: RSSEngine not available")
            return False
        
        print("[NewsEngine] Fetching news from RSS sources...")
        
        try:
            rss = RSSEngine(config_path=rss_config_path, use_database=False)
            
            # Fetch from all configured sources
            all_items = []
            for source in rss.sources:
                items = rss.fetch_feed(source['url'])
                if items:
                    # Add source info
                    for item in items:
                        item['source'] = source.get('name', source['url'])
                        item['category'] = source.get('category', 'general')
                    all_items.extend(items)
            
            if all_items:
                return self.store_news(all_items, source='rss_aggregated')
            else:
                print("[NewsEngine] No RSS items fetched")
                return False
                
        except Exception as e:
            print(f"[NewsEngine] ERROR: RSS integration failed: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored news
        
        Returns:
            Dictionary with statistics
        """
        if not self.db:
            return {'error': 'No database connection'}
        
        try:
            df = self.db.query_news_data()
            
            if df.empty:
                return {'total_items': 0}
            
            stats = {
                'total_items': len(df),
                'date_range': {
                    'start': df['timestamp'].min(),
                    'end': df['timestamp'].max()
                },
                'sources': df['source'].value_counts().to_dict(),
                'categories': df['category'].value_counts().to_dict(),
                'timezone_aware': df['timestamp'].apply(lambda x: x.tzinfo is not None).all(),
                'all_utc': df['timestamp'].apply(lambda x: x.tzinfo == timezone.utc).all() if df['timestamp'].apply(lambda x: x.tzinfo is not None).all() else False
            }
            
            return stats
            
        except Exception as e:
            return {'error': str(e)}


if __name__ == "__main__":
    # Test the news engine
    print("=" * 80)
    print("News Engine Test")
    print("=" * 80)
    
    # Initialize
    engine = NewsEngine(strict_validation=True)
    
    # Test data
    test_news = [
        {
            'timestamp': datetime.now(timezone.utc),
            'title': 'Bitcoin reaches new high',
            'description': 'BTC hits $100k for the first time',
            'link': 'https://example.com/btc-100k',
            'source': 'test_source',
            'cryptos_mentioned': 'BTC'
        },
        {
            'timestamp': '2025-11-13T12:00:00Z',
            'title': 'Ethereum upgrade complete',
            'source': 'test_source',
            'cryptos_mentioned': 'ETH'
        },
        {
            # Invalid - no timestamp
            'title': 'Invalid news item',
            'source': 'test_source'
        }
    ]
    
    print("\n Testing validation...")
    result = engine.store_news(test_news, source='test')
    
    print(f"\n✓ Storage result: {result}")
    
    # Get statistics
    print("\nDatabase statistics:")
    stats = engine.get_statistics()
    print(json.dumps(stats, indent=2, default=str))
