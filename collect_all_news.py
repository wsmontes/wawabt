#!/usr/bin/env python3
"""
Collect all finance news from all RSS sources and populate the database
Supports both general finance sources and stock-specific sources
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime
import time
from typing import List, Dict, Any

# Add root to path
sys.path.insert(0, os.path.abspath('.'))

from engines.rss import RSSEngine
from engines.smart_db import SmartDatabaseManager


class NewsCollector:
    """Collect and store news from multiple RSS sources"""
    
    def __init__(self, 
                 general_sources: str = "config/rss_sources.json",
                 stock_sources: str = "config/rss_stocks.json",
                 use_smart_db: bool = True):
        """
        Initialize the news collector
        
        Args:
            general_sources: Path to general finance RSS config
            stock_sources: Path to stock-specific RSS config
            use_smart_db: Use SmartDatabaseManager (True recommended)
        """
        self.general_sources = general_sources
        self.stock_sources = stock_sources
        self.use_smart_db = use_smart_db
        
        # Statistics
        self.stats = {
            'total_sources': 0,
            'successful_sources': 0,
            'failed_sources': 0,
            'total_entries': 0,
            'total_saved': 0,
            'sources_processed': [],
            'sources_failed': [],
            'start_time': datetime.now(),
            'end_time': None
        }
    
    def load_sources(self) -> List[Dict[str, Any]]:
        """Load all RSS sources from config files"""
        all_sources = []
        
        # Load general finance sources
        if Path(self.general_sources).exists():
            try:
                with open(self.general_sources, 'r') as f:
                    config = json.load(f)
                    sources = config.get('sources', [])
                    all_sources.extend(sources)
                    print(f"✓ Loaded {len(sources)} general finance sources")
            except Exception as e:
                print(f"⚠️  Error loading {self.general_sources}: {e}")
        
        # Load stock-specific sources
        if Path(self.stock_sources).exists():
            try:
                with open(self.stock_sources, 'r') as f:
                    config = json.load(f)
                    feeds = config.get('feeds', {})
                    
                    # Flatten nested structure
                    for category, feed_list in feeds.items():
                        for feed in feed_list:
                            source = {
                                'name': feed.get('name', 'Unknown'),
                                'url': feed.get('url', ''),
                                'category': category,
                                'update_frequency': feed.get('update_frequency', 'daily')
                            }
                            if source['url']:
                                all_sources.append(source)
                    
                    print(f"✓ Loaded {len(all_sources) - len(sources)} stock-specific sources")
            except Exception as e:
                print(f"⚠️  Error loading {self.stock_sources}: {e}")
        
        self.stats['total_sources'] = len(all_sources)
        return all_sources
    
    def collect_from_source(self, source: Dict[str, Any], rss_engine: RSSEngine) -> int:
        """
        Collect news from a single source
        
        Returns:
            Number of entries collected
        """
        name = source.get('name', 'Unknown')
        url = source.get('url', '')
        category = source.get('category', 'general')
        
        if not url:
            print(f"⚠️  Skipping {name} - no URL")
            self.stats['failed_sources'] += 1
            self.stats['sources_failed'].append({'name': name, 'reason': 'No URL'})
            return 0
        
        try:
            print(f"\n📰 Fetching: {name} ({category})")
            print(f"   URL: {url[:60]}...")
            
            # Fetch feed
            feed = rss_engine.fetch_feed(url, use_proxy=False)
            
            if not feed or not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"   ❌ No entries found")
                self.stats['failed_sources'] += 1
                self.stats['sources_failed'].append({'name': name, 'reason': 'No entries'})
                return 0
            
            # Parse entries
            entries = rss_engine.parse_feed_entries(feed, name, category)
            
            if not entries:
                print(f"   ❌ Failed to parse entries")
                self.stats['failed_sources'] += 1
                self.stats['sources_failed'].append({'name': name, 'reason': 'Parse error'})
                return 0
            
            # Save to database
            df = rss_engine.to_dataframe(entries)
            if df is not None and len(df) > 0:
                if hasattr(rss_engine.db, 'store_news_data'):
                    saved_files = rss_engine.db.store_news_data(df, source=name)
                    print(f"   ✅ Saved {len(entries)} entries to {len(saved_files)} file(s)")
                else:
                    print(f"   ⚠️  Database not configured")
                
                self.stats['successful_sources'] += 1
                self.stats['total_entries'] += len(entries)
                self.stats['total_saved'] += len(entries)
                self.stats['sources_processed'].append({
                    'name': name,
                    'category': category,
                    'entries': len(entries)
                })
                
                return len(entries)
            else:
                print(f"   ❌ Failed to convert to DataFrame")
                self.stats['failed_sources'] += 1
                self.stats['sources_failed'].append({'name': name, 'reason': 'DataFrame error'})
                return 0
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            self.stats['failed_sources'] += 1
            self.stats['sources_failed'].append({'name': name, 'reason': str(e)[:50]})
            return 0
    
    def collect_all(self, delay_between_sources: float = 0.5) -> Dict[str, Any]:
        """
        Collect news from all sources
        
        Args:
            delay_between_sources: Delay in seconds between source requests
            
        Returns:
            Statistics dictionary
        """
        print("="*70)
        print(" COLLECTING ALL FINANCE NEWS")
        print("="*70)
        print(f"\nStart time: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Load all sources
        all_sources = self.load_sources()
        
        if not all_sources:
            print("❌ No sources found!")
            return self.stats
        
        print(f"\n📊 Total sources to process: {len(all_sources)}")
        print("="*70)
        
        # Initialize RSS engine
        try:
            rss_engine = RSSEngine(
                config_path=self.general_sources,
                use_database=True,
                use_smart_db=self.use_smart_db
            )
        except Exception as e:
            print(f"❌ Failed to initialize RSS engine: {e}")
            return self.stats
        
        # Process each source
        for i, source in enumerate(all_sources, 1):
            print(f"\n[{i}/{len(all_sources)}]", end=" ")
            self.collect_from_source(source, rss_engine)
            
            # Delay between requests to be polite
            if i < len(all_sources):
                time.sleep(delay_between_sources)
        
        # Finalize stats
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        self.stats['duration_seconds'] = duration
        
        return self.stats
    
    def print_summary(self):
        """Print collection summary"""
        print("\n" + "="*70)
        print(" COLLECTION SUMMARY")
        print("="*70)
        
        print(f"\n⏱️  Duration: {self.stats.get('duration_seconds', 0):.1f} seconds")
        print(f"\n📊 Sources:")
        print(f"   Total:      {self.stats['total_sources']}")
        print(f"   Successful: {self.stats['successful_sources']} ✅")
        print(f"   Failed:     {self.stats['failed_sources']} ❌")
        
        print(f"\n📰 Entries:")
        print(f"   Total collected: {self.stats['total_entries']}")
        print(f"   Total saved:     {self.stats['total_saved']}")
        
        if self.stats['sources_processed']:
            print(f"\n✅ Successful Sources:")
            for source in self.stats['sources_processed']:
                print(f"   • {source['name']}: {source['entries']} entries ({source['category']})")
        
        if self.stats['sources_failed']:
            print(f"\n❌ Failed Sources ({len(self.stats['sources_failed'])}):")
            for source in self.stats['sources_failed'][:10]:  # Show first 10
                print(f"   • {source['name']}: {source['reason']}")
            
            if len(self.stats['sources_failed']) > 10:
                print(f"   ... and {len(self.stats['sources_failed']) - 10} more")
        
        # Database statistics
        print(f"\n💾 Database Status:")
        try:
            smart_db = SmartDatabaseManager()
            all_data = smart_db.query_news_data()
            
            if not all_data.empty:
                print(f"   Total records in DB: {len(all_data)}")
                
                sources = all_data['source'].value_counts()
                print(f"   Unique sources: {len(sources)}")
                
                print(f"\n   Top 5 sources by volume:")
                for source, count in sources.head(5).items():
                    print(f"   • {source}: {count} records")
            else:
                print("   No data in database")
        except Exception as e:
            print(f"   ⚠️  Could not query database: {e}")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect all finance news from RSS sources')
    parser.add_argument('--general', default='config/rss_sources.json',
                       help='Path to general RSS sources config')
    parser.add_argument('--stocks', default='config/rss_stocks.json',
                       help='Path to stock-specific RSS sources config')
    parser.add_argument('--delay', type=float, default=0.5,
                       help='Delay between source requests (seconds)')
    parser.add_argument('--no-smart-db', action='store_true',
                       help='Disable SmartDatabaseManager (use legacy)')
    
    args = parser.parse_args()
    
    # Create collector
    collector = NewsCollector(
        general_sources=args.general,
        stock_sources=args.stocks,
        use_smart_db=not args.no_smart_db
    )
    
    # Collect all news
    try:
        stats = collector.collect_all(delay_between_sources=args.delay)
        collector.print_summary()
        
        # Exit code based on success
        if stats['successful_sources'] > 0:
            print(f"\n✅ Collection completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ No sources were successfully collected")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        collector.print_summary()
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
