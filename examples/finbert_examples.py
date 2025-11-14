#!/usr/bin/env python3
"""
Example usage of FinBERT Engine
Demonstrates sentiment analysis on news data
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from engines.finbert import FinBERTEngine
from engines.smart_db import SmartDatabaseManager


def example_single_text():
    """Example: Analyze single text"""
    print("="*70)
    print(" EXAMPLE 1: Single Text Analysis")
    print("="*70)
    print()
    
    engine = FinBERTEngine(use_smart_db=False)
    
    texts = [
        "Apple stock soars to record high on strong iPhone sales",
        "Market crash: Investors flee as recession fears mount",
        "The Federal Reserve announced interest rate decision today",
        "Bitcoin surges past $100k as institutional adoption grows"
    ]
    
    for text in texts:
        result = engine.analyze_sentiment(text)
        
        print(f"Text: {text}")
        print(f"Sentiment: {result['sentiment'].upper()} ({result['confidence']:.1%} confidence)")
        print(f"Scores: +{result['scores']['positive']:.2f} / -{result['scores']['negative']:.2f} / ={result['scores']['neutral']:.2f}")
        print()


def example_news_analysis():
    """Example: Analyze news from database"""
    print("="*70)
    print(" EXAMPLE 2: News Database Analysis")
    print("="*70)
    print()
    
    engine = FinBERTEngine(use_smart_db=True)
    
    # Get recent news
    smart_db = SmartDatabaseManager()
    news_df = smart_db.query_news_data(source='CoinDesk')
    
    if news_df.empty:
        print("No news found. Try running: python collect_all_news.py")
        return
    
    print(f"Analyzing {len(news_df)} articles from CoinDesk...")
    print()
    
    # Analyze sentiment
    result_df = engine.analyze_news_df(news_df.head(10))
    
    # Show results
    for idx, row in result_df.head(5).iterrows():
        print(f"Title: {row['title'][:70]}...")
        print(f"Sentiment: {row['sentiment']} ({row['sentiment_confidence']:.1%})")
        print(f"Date: {row['timestamp']}")
        print()


def example_save_analysis():
    """Example: Analyze and save to database"""
    print("="*70)
    print(" EXAMPLE 3: Analyze and Save to Database")
    print("="*70)
    print()
    
    engine = FinBERTEngine(use_smart_db=True)
    
    # Analyze last 100 news articles and save
    result_df = engine.analyze_and_save(
        source='CoinDesk',
        limit=100
    )
    
    if not result_df.empty:
        print(f"✅ Analyzed and saved {len(result_df)} articles")
        
        # Show distribution
        print("\nSentiment Distribution:")
        print(f"  Positive: {(result_df['sentiment'] == 'positive').sum()}")
        print(f"  Negative: {(result_df['sentiment'] == 'negative').sum()}")
        print(f"  Neutral: {(result_df['sentiment'] == 'neutral').sum()}")


def example_sentiment_summary():
    """Example: Get sentiment summary"""
    print("="*70)
    print(" EXAMPLE 4: Sentiment Summary")
    print("="*70)
    print()
    
    engine = FinBERTEngine(use_smart_db=True)
    
    summary = engine.get_sentiment_summary(source='CoinDesk')
    
    print(f"CoinDesk Sentiment Summary:")
    print(f"  Total articles: {summary['total']}")
    print(f"  Positive: {summary['positive']} ({summary['positive_pct']:.1f}%)")
    print(f"  Negative: {summary['negative']} ({summary['negative_pct']:.1f}%)")
    print(f"  Neutral: {summary['neutral']} ({summary['neutral_pct']:.1f}%)")
    print(f"  Average confidence: {summary['avg_confidence']:.1%}")


def main():
    """Run all examples"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinBERT Examples')
    parser.add_argument('--example', type=int, choices=[1, 2, 3, 4],
                       help='Run specific example (1-4)')
    
    args = parser.parse_args()
    
    try:
        if args.example == 1:
            example_single_text()
        elif args.example == 2:
            example_news_analysis()
        elif args.example == 3:
            example_save_analysis()
        elif args.example == 4:
            example_sentiment_summary()
        else:
            # Run all examples
            example_single_text()
            print("\n")
            example_news_analysis()
            print("\n")
            example_save_analysis()
            print("\n")
            example_sentiment_summary()
            
    except ImportError as e:
        print(f"\n❌ Error: {e}")
        print("\nPlease install dependencies first:")
        print("   bash install_finbert.sh")
        print("   # or")
        print("   pip install torch transformers")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
