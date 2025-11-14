"""
RSS Engine for retrieving RSS feed data
Supports proxy rotation and multiple RSS sources
"""
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
import random

try:
    from .database import DatabaseEngine
    from .smart_db import SmartDatabaseManager
except ImportError:
    DatabaseEngine = None
    SmartDatabaseManager = None

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None


class RSSEngine:
    """
    RSS feed reader with proxy support and configurable sources
    """
    
    def __init__(self, config_path: str = "config/rss_sources.json",
                 use_database: bool = True,
                 db_config_path: str = "config/database.json",
                 use_smart_db: bool = True):
        """
        Initialize the RSS engine
        
        Args:
            config_path: Path to the RSS configuration JSON file
            use_database: Whether to enable database integration
            db_config_path: Path to database configuration
            use_smart_db: Use SmartDatabaseManager (recommended) vs legacy DatabaseEngine
        """
        if feedparser is None:
            raise RuntimeError("feedparser not installed. Install with: pip install feedparser")
        
        self.config = self._load_config(config_path)
        
        # Support both "sources" and "feeds" formats
        if "sources" in self.config:
            self.sources = self.config.get("sources", [])
        elif "feeds" in self.config:
            # Convert nested feeds structure to flat sources list
            feeds = self.config.get("feeds", {})
            self.sources = []
            for category, feed_list in feeds.items():
                for feed in feed_list:
                    source = {
                        'name': feed.get('name', 'Unknown'),
                        'url': feed.get('url', ''),
                        'category': category
                    }
                    self.sources.append(source)
            print(f"Loaded {len(self.sources)} feeds from '{config_path}' (nested format)")
        else:
            self.sources = []
        
        self.proxy_config = self.config.get("proxies", {})
        self.settings = self.config.get("settings", {})
        
        self.session = self._create_session()
        self.proxy_index = 0
        
        # Initialize database if enabled
        self.db = None
        self.use_database = use_database
        if use_database:
            if use_smart_db and SmartDatabaseManager is not None:
                try:
                    self.db = SmartDatabaseManager(db_config_path)
                    print("Smart Database integration enabled for RSS")
                except Exception as e:
                    print(f"Failed to initialize Smart Database: {e}")
                    self.db = None
            elif DatabaseEngine is not None:
                try:
                    self.db = DatabaseEngine(db_config_path)
                    print("Database integration enabled for RSS")
                except Exception as e:
                    print(f"Failed to initialize database: {e}")
                    self.db = None
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "sources": [],
            "proxies": {
                "enabled": False,
                "proxy_list": [],
                "rotation": "round-robin"
            },
            "settings": {
                "timeout": 30,
                "max_retries": 3,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "update_interval_minutes": 15
            }
        }
    
    def _create_session(self) -> Optional[requests.Session]:
        """Create a requests session with retry logic"""
        if requests is None:
            return None
        
        session = requests.Session()
        
        # Configure retry strategy
        max_retries = self.settings.get("max_retries", 3)
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set user agent
        user_agent = self.settings.get("user_agent", "RSS Reader")
        session.headers.update({"User-Agent": user_agent})
        
        return session
    
    def _get_proxy(self) -> Optional[Dict[str, str]]:
        """Get the next proxy based on rotation strategy"""
        if not self.proxy_config.get("enabled", False):
            return None
        
        proxy_list = self.proxy_config.get("proxy_list", [])
        if not proxy_list:
            return None
        
        rotation = self.proxy_config.get("rotation", "round-robin")
        
        if rotation == "round-robin":
            proxy = proxy_list[self.proxy_index % len(proxy_list)]
            self.proxy_index += 1
        elif rotation == "random":
            proxy = random.choice(proxy_list)
        else:
            proxy = proxy_list[0]
        
        return {
            "http": proxy,
            "https": proxy
        }
    
    def fetch_feed(self, url: str, use_proxy: bool = None) -> Optional[feedparser.FeedParserDict]:
        """
        Fetch and parse an RSS feed
        
        Args:
            url: URL of the RSS feed
            use_proxy: Whether to use proxy (None uses config default)
        
        Returns:
            Parsed feed object or None if failed
        """
        try:
            timeout = self.settings.get("timeout", 30)
            
            # Determine if proxy should be used
            if use_proxy is None:
                use_proxy = self.proxy_config.get("enabled", False)
            
            # Fetch with or without proxy
            if use_proxy and self.session:
                proxy = self._get_proxy()
                response = self.session.get(url, timeout=timeout, proxies=proxy)
                feed = feedparser.parse(response.content)
            else:
                feed = feedparser.parse(url)
            
            return feed
            
        except Exception as e:
            print(f"Error fetching feed from {url}: {e}")
            return None
    
    def parse_feed_entries(self, feed: feedparser.FeedParserDict, 
                          source_name: str = "Unknown",
                          category: str = "general") -> List[Dict[str, Any]]:
        """
        Parse feed entries into structured data
        
        Args:
            feed: Parsed feed object
            source_name: Name of the feed source
            category: Category of the feed
        
        Returns:
            List of parsed entries
        """
        entries = []
        
        for entry in feed.entries:
            try:
                # Extract published date - ensure timezone-aware UTC timestamps
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                else:
                    # Skip entries without valid timestamps
                    continue
                
                # Extract entry data
                entry_data = {
                    'timestamp': published,
                    'source': source_name,
                    'category': category,
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('summary', entry.get('description', '')),
                    'author': entry.get('author', ''),
                    'tags': ', '.join([tag.term for tag in entry.get('tags', [])]) if entry.get('tags') else ''
                }
                
                entries.append(entry_data)
                
            except Exception as e:
                print(f"Error parsing entry: {e}")
                continue
        
        return entries
    
    def fetch_all_sources(self, use_proxy: bool = None, save_to_db: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all RSS sources from configuration
        
        Args:
            use_proxy: Whether to use proxy for all requests
            save_to_db: Whether to save data to database
        
        Returns:
            List of all parsed entries from all sources
        """
        all_entries = []
        
        for source in self.sources:
            name = source.get('name', 'Unknown')
            url = source.get('url', '')
            category = source.get('category', 'general')
            
            if not url:
                print(f"Skipping source '{name}' - no URL provided")
                continue
            
            print(f"Fetching {name}...")
            feed = self.fetch_feed(url, use_proxy)
            
            if feed:
                entries = self.parse_feed_entries(feed, name, category)
                all_entries.extend(entries)
                print(f"  → Retrieved {len(entries)} entries")
            else:
                print(f"  → Failed to retrieve feed")
            
            # Small delay between requests to be polite
            time.sleep(0.5)
        
        # Save to database if enabled
        if save_to_db and all_entries and self.db:
            try:
                df = self.to_dataframe(all_entries)
                if df is not None:
                    # Use smart database for better organization
                    if hasattr(self.db, 'store_news_data'):
                        # Group by source and store separately
                        for source in df['source'].unique():
                            source_df = df[df['source'] == source]
                            self.db.store_news_data(source_df, source=source)
                    else:
                        # Fallback to legacy database
                        table_name = "rss_feeds"
                        self.db.insert_dataframe(table_name, df, if_exists='append')
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"rss_feeds_{timestamp}"
                        self.db.save_to_parquet(df, filename)
                    print(f"RSS data saved to database")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return all_entries
    
    def fetch_feed_by_name(self, name: str, use_proxy: bool = None, 
                          save_to_db: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch RSS feed by source name
        
        Args:
            name: Name of the source to fetch
            use_proxy: Whether to use proxy
            save_to_db: Whether to save data to database
        
        Returns:
            List of parsed entries from matching source
        """
        # Find source by name
        source = None
        for s in self.sources:
            if s.get('name') == name:
                source = s
                break
        
        if not source:
            print(f"Source '{name}' not found in configuration")
            return []
        
        url = source.get('url', '')
        category = source.get('category', 'general')
        
        feed = self.fetch_feed(url, use_proxy)
        
        if not feed:
            return []
        
        entries = self.parse_feed_entries(feed, name, category)
        
        # Save to database if enabled
        if save_to_db and entries and self.db:
            try:
                df = self.to_dataframe(entries)
                if df is not None:
                    if hasattr(self.db, 'store_news_data'):
                        self.db.store_news_data(df, source=name)
                    else:
                        table_name = "rss_feeds"
                        self.db.insert_dataframe(table_name, df, if_exists='append')
                    print(f"RSS data saved to database")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return entries
    
    def fetch_by_category(self, category: str, use_proxy: bool = None, 
                         save_to_db: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch RSS feeds filtered by category
        
        Args:
            category: Category to filter by
            use_proxy: Whether to use proxy
            save_to_db: Whether to save data to database
        
        Returns:
            List of parsed entries from matching category
        """
        all_entries = []
        
        filtered_sources = [s for s in self.sources if s.get('category') == category]
        
        for source in filtered_sources:
            name = source.get('name', 'Unknown')
            url = source.get('url', '')
            
            print(f"Fetching {name}...")
            feed = self.fetch_feed(url, use_proxy)
            
            if feed:
                entries = self.parse_feed_entries(feed, name, category)
                all_entries.extend(entries)
                print(f"  → Retrieved {len(entries)} entries")
        
        # Save to database if enabled
        if save_to_db and all_entries and self.db:
            try:
                df = self.to_dataframe(all_entries)
                if df is not None:
                    if hasattr(self.db, 'store_news_data'):
                        # Smart database - store by source
                        for source in df['source'].unique():
                            source_df = df[df['source'] == source]
                            self.db.store_news_data(source_df, source=f"{source}_{category}")
                    else:
                        # Legacy database
                        table_name = f"rss_{category}"
                        self.db.insert_dataframe(table_name, df, if_exists='append')
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"rss_{category}_{timestamp}"
                        self.db.save_to_parquet(df, filename)
                    print(f"RSS data saved to database")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return all_entries
    
    def get_sources_list(self) -> List[Dict[str, str]]:
        """Get list of configured RSS sources"""
        return [
            {
                'name': s.get('name', 'Unknown'),
                'url': s.get('url', ''),
                'category': s.get('category', 'general')
            }
            for s in self.sources
        ]
    
    def get_categories(self) -> List[str]:
        """Get list of unique categories"""
        categories = set()
        for source in self.sources:
            categories.add(source.get('category', 'general'))
        return sorted(list(categories))
    
    def add_source(self, name: str, url: str, category: str = "general"):
        """Add a new RSS source (runtime only, not saved to config)"""
        self.sources.append({
            'name': name,
            'url': url,
            'category': category
        })
        print(f"Added source: {name}")
    
    def save_config(self, config_path: Optional[str] = None):
        """
        Save current configuration to file
        
        Args:
            config_path: Path to save config (uses original path if not provided)
        """
        if config_path is None:
            config_path = "config/rss_sources.json"
        
        with open(config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        print(f"Configuration saved to {config_path}")
    
    def query_saved_data(self, table_name: str = "rss_feeds", 
                        sql_filter: Optional[str] = None) -> Optional[Any]:
        """
        Query saved RSS data from database
        
        Args:
            table_name: Name of the table to query
            sql_filter: Optional SQL WHERE clause filter
        
        Returns:
            DataFrame with query results or None if database not available
        """
        if not self.db:
            print("Database not initialized")
            return None
        
        try:
            if sql_filter:
                return self.db.query(f"SELECT * FROM {table_name} WHERE {sql_filter}")
            else:
                return self.db.query(f"SELECT * FROM {table_name}")
        except Exception as e:
            print(f"Query failed: {e}")
            return None
    
    def list_saved_tables(self) -> List[str]:
        """List all saved RSS data tables"""
        if not self.db:
            return []
        # Filter tables that start with 'rss_'
        all_tables = self.db.list_tables()
        return [t for t in all_tables if t.startswith('rss_')]
    
    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()
            print("Database connection closed")
    
    def to_dataframe(self, entries: List[Dict[str, Any]]):
        """
        Convert entries to pandas DataFrame
        
        Args:
            entries: List of parsed RSS entries
        
        Returns:
            DataFrame with RSS data
        """
        try:
            import pandas as pd
            df = pd.DataFrame(entries)
            return df
        except ImportError:
            print("pandas not installed. Install with: pip install pandas")
            return None


def main():
    """CLI interface for RSS engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RSS Engine CLI for retrieving RSS feed data')
    parser.add_argument('--config', default='config/rss_sources.json', help='Path to config file')
    parser.add_argument('--no-db', action='store_true', help='Disable database integration')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List sources command
    subparsers.add_parser('list-sources', help='List configured RSS sources')
    
    # List categories command
    subparsers.add_parser('list-categories', help='List all categories')
    
    # Fetch all command
    fetch_all_parser = subparsers.add_parser('fetch-all', help='Fetch all RSS sources')
    fetch_all_parser.add_argument('--proxy', action='store_true', help='Use proxy')
    fetch_all_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    fetch_all_parser.add_argument('--output', help='Output file path (csv/parquet/json)')
    
    # Fetch by category command
    fetch_cat_parser = subparsers.add_parser('fetch-category', help='Fetch RSS feeds by category')
    fetch_cat_parser.add_argument('category', help='Category to fetch')
    fetch_cat_parser.add_argument('--proxy', action='store_true', help='Use proxy')
    fetch_cat_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    fetch_cat_parser.add_argument('--output', help='Output file path')
    
    # Fetch single source command
    fetch_one_parser = subparsers.add_parser('fetch-url', help='Fetch single RSS feed URL')
    fetch_one_parser.add_argument('url', help='RSS feed URL')
    fetch_one_parser.add_argument('--name', default='Custom Feed', help='Feed name')
    fetch_one_parser.add_argument('--category', default='general', help='Feed category')
    fetch_one_parser.add_argument('--proxy', action='store_true', help='Use proxy')
    fetch_one_parser.add_argument('--output', help='Output file path')
    
    # Add source command
    add_parser = subparsers.add_parser('add-source', help='Add new RSS source')
    add_parser.add_argument('name', help='Source name')
    add_parser.add_argument('url', help='RSS feed URL')
    add_parser.add_argument('--category', default='general', help='Category')
    add_parser.add_argument('--save-config', action='store_true', help='Save to config file')
    
    # List saved tables command
    subparsers.add_parser('list-tables', help='List saved RSS data tables')
    
    # Query saved data command
    query_parser = subparsers.add_parser('query', help='Query saved RSS data')
    query_parser.add_argument('--table', default='rss_feeds', help='Table name to query')
    query_parser.add_argument('--filter', help='SQL WHERE clause filter')
    query_parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize RSS engine
    rss = RSSEngine(args.config, use_database=not args.no_db)
    
    try:
        if args.command == 'list-sources':
            sources = rss.get_sources_list()
            print(f"Configured sources ({len(sources)}):")
            for source in sources:
                print(f"  - [{source['category']}] {source['name']}")
                print(f"    {source['url']}")
        
        elif args.command == 'list-categories':
            categories = rss.get_categories()
            print(f"Categories ({len(categories)}):")
            for cat in categories:
                print(f"  - {cat}")
        
        elif args.command == 'fetch-all':
            entries = rss.fetch_all_sources(
                use_proxy=args.proxy,
                save_to_db=not args.no_save
            )
            print(f"\nTotal entries retrieved: {len(entries)}")
            if entries:
                print("\nSample entries:")
                for entry in entries[:5]:
                    print(f"  - [{entry['source']}] {entry['title']}")
                
                if args.output:
                    df = rss.to_dataframe(entries)
                    if df is not None:
                        _save_output(df, args.output)
        
        elif args.command == 'fetch-category':
            entries = rss.fetch_by_category(
                args.category,
                use_proxy=args.proxy,
                save_to_db=not args.no_save
            )
            print(f"\nTotal entries retrieved: {len(entries)}")
            if entries and args.output:
                df = rss.to_dataframe(entries)
                if df is not None:
                    _save_output(df, args.output)
        
        elif args.command == 'fetch-url':
            feed = rss.fetch_feed(args.url, use_proxy=args.proxy)
            if feed:
                entries = rss.parse_feed_entries(feed, args.name, args.category)
                print(f"Retrieved {len(entries)} entries from {args.name}")
                if entries and args.output:
                    df = rss.to_dataframe(entries)
                    if df is not None:
                        _save_output(df, args.output)
        
        elif args.command == 'add-source':
            rss.add_source(args.name, args.url, args.category)
            if args.save_config:
                rss.save_config()
        
        elif args.command == 'list-tables':
            tables = rss.list_saved_tables()
            print(f"Saved RSS tables ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        
        elif args.command == 'query':
            df = rss.query_saved_data(args.table, args.filter)
            if df is not None:
                print(df)
                if args.output:
                    _save_output(df, args.output)
    
    finally:
        rss.close()


def _save_output(df, output_path):
    """Helper function to save DataFrame to file"""
    if output_path.endswith('.csv'):
        df.to_csv(output_path, index=False)
    elif output_path.endswith('.parquet'):
        df.to_parquet(output_path, index=False)
    elif output_path.endswith('.json'):
        df.to_json(output_path, orient='records', date_format='iso')
    print(f"Data saved to {output_path}")


if __name__ == "__main__":
    main()
