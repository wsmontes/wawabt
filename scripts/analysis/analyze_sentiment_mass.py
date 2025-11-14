#!/usr/bin/env python3
"""
Mass Sentiment Analysis with Checkpoint/Resume
Analyzes all news in database with automatic resume capability
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import json
import logging
from time import sleep
from typing import Optional, Dict

sys.path.insert(0, os.path.abspath('.'))

from engines.finbert import FinBERTEngine
from engines.smart_db import SmartDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('sentiment_analysis_mass.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manage checkpoints for resumable processing"""
    
    def __init__(self, checkpoint_file: str = 'sentiment_checkpoint.json'):
        self.checkpoint_file = Path(checkpoint_file)
        self.checkpoint = self._load_checkpoint()
    
    def _load_checkpoint(self) -> Dict:
        """Load checkpoint from file"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                logger.info(f"📂 Loaded checkpoint: {len(checkpoint.get('processed', []))} sources processed")
                return checkpoint
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
                return self._create_new_checkpoint()
        else:
            return self._create_new_checkpoint()
    
    def _create_new_checkpoint(self) -> Dict:
        """Create new checkpoint structure"""
        return {
            'started_at': datetime.now().isoformat(),
            'last_update': None,
            'processed': [],  # List of processed sources
            'failed': [],  # List of failed sources with errors
            'stats': {
                'total_sources': 0,
                'total_articles': 0,
                'total_analyzed': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0
            }
        }
    
    def save(self):
        """Save checkpoint to file"""
        self.checkpoint['last_update'] = datetime.now().isoformat()
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint, f, indent=2)
            logger.debug("💾 Checkpoint saved")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def is_processed(self, source: str) -> bool:
        """Check if source was already processed"""
        return source in self.checkpoint['processed']
    
    def mark_processed(self, source: str, stats: Dict):
        """Mark source as processed with stats"""
        if source not in self.checkpoint['processed']:
            self.checkpoint['processed'].append(source)
        
        # Update global stats (convert to int for JSON serialization)
        self.checkpoint['stats']['total_articles'] += int(stats.get('total', 0))
        self.checkpoint['stats']['total_analyzed'] += int(stats.get('analyzed', 0))
        self.checkpoint['stats']['positive'] += int(stats.get('positive', 0))
        self.checkpoint['stats']['negative'] += int(stats.get('negative', 0))
        self.checkpoint['stats']['neutral'] += int(stats.get('neutral', 0))
        
        self.save()
    
    def mark_failed(self, source: str, error: str):
        """Mark source as failed"""
        failed_entry = {
            'source': source,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        }
        self.checkpoint['failed'].append(failed_entry)
        self.save()
    
    def get_stats(self) -> Dict:
        """Get current statistics"""
        return self.checkpoint['stats']
    
    def reset(self):
        """Reset checkpoint"""
        self.checkpoint = self._create_new_checkpoint()
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        logger.info("🔄 Checkpoint reset")


class MassSentimentAnalyzer:
    """Mass sentiment analysis with checkpoint support"""
    
    def __init__(self, checkpoint_file: str = 'sentiment_checkpoint.json',
                 batch_size: int = 100, delay: float = 0.1):
        """
        Initialize mass analyzer
        
        Args:
            checkpoint_file: Path to checkpoint file
            batch_size: Number of articles to process per batch
            delay: Delay between batches (seconds)
        """
        self.checkpoint_mgr = CheckpointManager(checkpoint_file)
        self.batch_size = batch_size
        self.delay = delay
        self.finbert = None
        self.smart_db = None
    
    def _init_engines(self):
        """Initialize engines (lazy loading)"""
        if self.finbert is None:
            logger.info("Initializing FinBERT engine...")
            self.finbert = FinBERTEngine(use_smart_db=True)
            self.smart_db = self.finbert.smart_db
    
    def get_all_sources(self) -> list:
        """Get list of all news sources in database"""
        if self.smart_db is None:
            self.smart_db = SmartDatabaseManager()
        
        try:
            all_news = self.smart_db.query_news_data()
            if all_news.empty:
                logger.warning("No news found in database")
                return []
            
            sources = all_news['source'].unique().tolist()
            logger.info(f"Found {len(sources)} unique sources in database")
            return sorted(sources)
        except Exception as e:
            logger.error(f"Error getting sources: {e}")
            return []
    
    def analyze_source(self, source: str) -> Optional[Dict]:
        """
        Analyze all articles from a specific source
        
        Args:
            source: News source name
            
        Returns:
            Statistics dictionary or None if failed
        """
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"📊 Analyzing source: {source}")
            logger.info(f"{'='*70}")
            
            # Query news for this source
            news_df = self.smart_db.query_news_data(source=source)
            
            if news_df.empty:
                logger.warning(f"  ⚠️  No articles found for {source}")
                return {'total': 0, 'analyzed': 0, 'positive': 0, 'negative': 0, 'neutral': 0}
            
            total_articles = len(news_df)
            logger.info(f"  Found {total_articles} articles")
            
            # Process in batches
            analyzed = 0
            positive = 0
            negative = 0
            neutral = 0
            
            for batch_start in range(0, total_articles, self.batch_size):
                batch_end = min(batch_start + self.batch_size, total_articles)
                batch_df = news_df.iloc[batch_start:batch_end]
                
                logger.info(f"  Processing batch {batch_start}-{batch_end}/{total_articles}")
                
                try:
                    # Analyze sentiment
                    result_df = self.finbert.analyze_news_df(batch_df)
                    
                    # Count sentiments
                    batch_positive = (result_df['sentiment'] == 'positive').sum()
                    batch_negative = (result_df['sentiment'] == 'negative').sum()
                    batch_neutral = (result_df['sentiment'] == 'neutral').sum()
                    
                    positive += batch_positive
                    negative += batch_negative
                    neutral += batch_neutral
                    analyzed += len(result_df)
                    
                    # Save batch results
                    sentiment_df = pd.DataFrame()
                    sentiment_df['timestamp'] = result_df['timestamp']
                    sentiment_df['source'] = result_df['source']
                    sentiment_df['title'] = result_df['title']
                    sentiment_df['link'] = result_df['link']
                    sentiment_df['sentiment'] = result_df['sentiment']
                    sentiment_df['confidence'] = result_df['sentiment_confidence']
                    sentiment_df['positive_score'] = result_df['sentiment_positive']
                    sentiment_df['negative_score'] = result_df['sentiment_negative']
                    sentiment_df['neutral_score'] = result_df['sentiment_neutral']
                    sentiment_df['analyzed_at'] = result_df['analyzed_at']
                    
                    if 'category' in result_df.columns:
                        sentiment_df['category'] = result_df['category']
                    
                    # Save to database
                    self.smart_db.store_analysis_data(
                        df=sentiment_df,
                        analysis_type='sentiment',
                        symbol=source
                    )
                    
                    logger.info(f"    ✓ Batch saved: +{batch_positive} -{batch_negative} ={batch_neutral}")
                    
                    # Delay between batches to avoid overheating
                    if batch_end < total_articles:
                        sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"    ❌ Error processing batch {batch_start}-{batch_end}: {e}")
                    # Continue with next batch
                    continue
            
            stats = {
                'total': total_articles,
                'analyzed': analyzed,
                'positive': positive,
                'negative': negative,
                'neutral': neutral
            }
            
            logger.info(f"  ✅ Completed: {analyzed}/{total_articles} articles")
            logger.info(f"     Positive: {positive} ({positive/analyzed*100:.1f}%)")
            logger.info(f"     Negative: {negative} ({negative/analyzed*100:.1f}%)")
            logger.info(f"     Neutral: {neutral} ({neutral/analyzed*100:.1f}%)")
            
            return stats
            
        except Exception as e:
            logger.error(f"  ❌ Error analyzing {source}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run(self, reset_checkpoint: bool = False):
        """
        Run mass sentiment analysis
        
        Args:
            reset_checkpoint: If True, start from scratch
        """
        if reset_checkpoint:
            self.checkpoint_mgr.reset()
        
        # Initialize engines
        self._init_engines()
        
        # Get all sources
        all_sources = self.get_all_sources()
        if not all_sources:
            logger.error("No sources found. Exiting.")
            return
        
        # Filter out already processed sources
        pending_sources = [s for s in all_sources if not self.checkpoint_mgr.is_processed(s)]
        
        if not pending_sources:
            logger.info("✅ All sources already processed!")
            self.print_summary()
            return
        
        logger.info(f"\n🚀 Starting mass sentiment analysis")
        logger.info(f"   Total sources: {len(all_sources)}")
        logger.info(f"   Already processed: {len(all_sources) - len(pending_sources)}")
        logger.info(f"   Pending: {len(pending_sources)}")
        logger.info(f"   Batch size: {self.batch_size}")
        logger.info(f"   Checkpoint file: {self.checkpoint_mgr.checkpoint_file}")
        logger.info("")
        
        # Update total sources in checkpoint
        self.checkpoint_mgr.checkpoint['stats']['total_sources'] = len(all_sources)
        self.checkpoint_mgr.save()
        
        # Process each source
        for i, source in enumerate(pending_sources, 1):
            logger.info(f"\n[{i}/{len(pending_sources)}] Processing: {source}")
            
            try:
                stats = self.analyze_source(source)
                
                if stats:
                    self.checkpoint_mgr.mark_processed(source, stats)
                else:
                    self.checkpoint_mgr.mark_failed(source, "Analysis returned None")
                
            except KeyboardInterrupt:
                logger.warning("\n⚠️  Process interrupted by user")
                logger.info("💾 Progress saved to checkpoint")
                logger.info("   Run again to resume from where it stopped")
                return
            
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                self.checkpoint_mgr.mark_failed(source, str(e))
                # Continue with next source
                continue
        
        logger.info("\n" + "="*70)
        logger.info(" MASS SENTIMENT ANALYSIS COMPLETED")
        logger.info("="*70)
        
        self.print_summary()
    
    def print_summary(self):
        """Print final summary"""
        stats = self.checkpoint_mgr.get_stats()
        checkpoint = self.checkpoint_mgr.checkpoint
        
        print("\n📊 SUMMARY")
        print("="*70)
        print(f"Started at:        {checkpoint['started_at']}")
        print(f"Last update:       {checkpoint.get('last_update', 'N/A')}")
        print(f"\nSources:")
        print(f"  Total:           {stats['total_sources']}")
        print(f"  Processed:       {len(checkpoint['processed'])}")
        print(f"  Failed:          {len(checkpoint['failed'])}")
        
        print(f"\nArticles:")
        print(f"  Total found:     {stats['total_articles']:,}")
        print(f"  Analyzed:        {stats['total_analyzed']:,}")
        
        if stats['total_analyzed'] > 0:
            print(f"\nSentiment Distribution:")
            print(f"  Positive:        {stats['positive']:,} ({stats['positive']/stats['total_analyzed']*100:.1f}%)")
            print(f"  Negative:        {stats['negative']:,} ({stats['negative']/stats['total_analyzed']*100:.1f}%)")
            print(f"  Neutral:         {stats['neutral']:,} ({stats['neutral']/stats['total_analyzed']*100:.1f}%)")
        
        if checkpoint['failed']:
            print(f"\n⚠️  Failed Sources:")
            for failed in checkpoint['failed'][:5]:
                print(f"  • {failed['source']}: {failed['error'][:60]}")
            if len(checkpoint['failed']) > 5:
                print(f"  ... and {len(checkpoint['failed']) - 5} more")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Mass Sentiment Analysis with Checkpoint')
    parser.add_argument('--reset', action='store_true',
                       help='Reset checkpoint and start from scratch')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='Number of articles per batch (default: 100)')
    parser.add_argument('--delay', type=float, default=0.1,
                       help='Delay between batches in seconds (default: 0.1)')
    parser.add_argument('--checkpoint-file', type=str, default='sentiment_checkpoint.json',
                       help='Path to checkpoint file')
    parser.add_argument('--summary', action='store_true',
                       help='Show summary of current progress and exit')
    
    args = parser.parse_args()
    
    analyzer = MassSentimentAnalyzer(
        checkpoint_file=args.checkpoint_file,
        batch_size=args.batch_size,
        delay=args.delay
    )
    
    if args.summary:
        analyzer.print_summary()
    else:
        try:
            analyzer.run(reset_checkpoint=args.reset)
        except KeyboardInterrupt:
            logger.info("\n\n⚠️  Interrupted by user")
            logger.info("💾 Progress saved. Run again to resume.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
