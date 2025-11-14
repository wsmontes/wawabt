"""
Populate database with historical news data (last 5 years)
Uses Hugging Face datasets for historical financial news
"""
import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from engines.datasets import DatasetsEngine
from engines.news import NewsEngine

# Major cryptocurrencies to track
MAJOR_CRYPTOS = [
    'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT', 'MATIC', 'AVAX',
    'SHIB', 'LTC', 'UNI', 'LINK', 'ATOM', 'ETC', 'XLM', 'ALGO', 'VET', 'FIL',
    'TRX', 'ICP', 'HBAR', 'APT', 'ARB', 'OP', 'SUI', 'INJ', 'STX', 'TON'
]

# Major stock symbols to track
MAJOR_STOCKS = [
    # Tech Giants
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'NFLX',
    # Finance
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'AXP', 'V', 'MA',
    # Other Major
    'WMT', 'JNJ', 'PG', 'UNH', 'HD', 'DIS', 'PFE', 'KO', 'PEP', 'MCD',
    'CSCO', 'ORCL', 'ADBE', 'CRM', 'IBM', 'QCOM', 'TXN', 'AVGO', 'NOW', 'SNOW',
    # ETFs
    'SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'VEA', 'VWO', 'AGG', 'GLD'
]

# Popular financial news datasets on Hugging Face
FINANCIAL_NEWS_DATASETS = [
    {
        'name': 'financial_phrasebank',
        'description': 'Financial news with sentiment labels',
        'path': 'financial_phrasebank',
        'split': 'train',
        'text_column': 'sentence',
        'sentiment_column': 'label'
    },
    {
        'name': 'reuters_financial',
        'description': 'Reuters financial news corpus',
        'path': 'SetFit/20_newsgroups',  # Contains financial topics
        'split': 'train',
        'text_column': 'text',
        'label_column': 'label'
    },
    {
        'name': 'crypto_news',
        'description': 'Cryptocurrency news dataset',
        'path': 'kz/crypto-news',  # If available
        'split': 'train',
        'text_column': 'text',
        'title_column': 'title'
    }
]

def populate_historical_news():
    """Populate database with 5 years of historical financial news"""
    
    print("=" * 100)
    print("HISTORICAL NEWS DATA POPULATION")
    print("=" * 100)
    print()
    print(f"Target: Last 5 years of financial news")
    print(f"Cryptos: {len(MAJOR_CRYPTOS)} major cryptocurrencies")
    print(f"Stocks: {len(MAJOR_STOCKS)} major stocks and ETFs")
    print()
    
    # Initialize engines
    datasets_engine = DatasetsEngine()
    news_engine = NewsEngine()
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=5*365)  # 5 years
    
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print()
    
    total_imported = 0
    
    # Strategy 1: Try to load popular financial news datasets
    print("=" * 100)
    print("STRATEGY 1: Loading Hugging Face Financial News Datasets")
    print("=" * 100)
    
    for dataset_info in FINANCIAL_NEWS_DATASETS:
        print(f"\n{'=' * 100}")
        print(f"Dataset: {dataset_info['name']}")
        print(f"Description: {dataset_info['description']}")
        print('=' * 100)
        
        try:
            # Try to load the dataset
            dataset = datasets_engine.load_huggingface_dataset(
                dataset_info['path'],
                split=dataset_info['split']
            )
            
            print(f"✓ Loaded dataset with {len(dataset)} entries")
            
            # Convert to DataFrame
            df = datasets_engine.huggingface_to_dataframe(dataset)
            
            # Process and prepare for storage
            news_df = prepare_dataset_for_storage(
                df, 
                dataset_info,
                start_date,
                end_date,
                dataset_info['name']
            )
            
            if not news_df.empty:
                # Store in database
                stored = news_engine.store_news(
                    news_df,
                    source=f"historical_{dataset_info['name']}"
                )
                
                print(f"✓ Stored {len(news_df)} news items")
                total_imported += len(news_df)
            else:
                print("⚠️  No relevant news items after filtering")
            
        except Exception as e:
            print(f"❌ Failed to load {dataset_info['name']}: {e}")
            continue
    
    # Strategy 2: Generate synthetic historical context from current RSS feeds
    print(f"\n{'=' * 100}")
    print("STRATEGY 2: Fetching ALL Current RSS Feeds (Crypto + Stocks)")
    print('=' * 100)
    
    from engines.rss import RSSEngine
    
    # Load crypto feeds
    print("\n--- Fetching Crypto News ---")
    crypto_rss = RSSEngine('config/rss.json')
    crypto_news = crypto_rss.fetch_all_sources(save_to_db=False)
    print(f"✓ Fetched {len(crypto_news)} crypto news items")
    
    # Load stock feeds
    print("\n--- Fetching Stock News ---")
    stock_rss = RSSEngine('config/rss_stocks.json')
    stock_news = stock_rss.fetch_all_sources(save_to_db=False)
    print(f"✓ Fetched {len(stock_news)} stock news items")
    
    # Combine and store
    all_current_news = crypto_news + stock_news
    print(f"\n✓ Total current news: {len(all_current_news)}")
    
    if all_current_news:
        df = pd.DataFrame(all_current_news)
        stored = news_engine.store_news(df, source="current_rss_feeds")
        print(f"✓ Stored {len(df)} current news items")
        total_imported += len(df)
    
    # Strategy 3: Try Kaggle datasets
    print(f"\n{'=' * 100}")
    print("STRATEGY 3: Checking Kaggle for Financial News Datasets")
    print('=' * 100)
    
    kaggle_datasets = [
        'aaron7sun/stocknews',
        'miguelcorraljr/sp500-stock-news-data',
        'jeet2016/financial-news-dataset',
        'notlucasp/financial-news-headlines',
    ]
    
    for dataset_ref in kaggle_datasets:
        try:
            print(f"\nTrying to download: {dataset_ref}")
            dataset_path = datasets_engine.download_kaggle_dataset(
                dataset_ref,
                unzip=True
            )
            
            # Find CSV files in the dataset
            csv_files = list(dataset_path.glob('*.csv'))
            
            for csv_file in csv_files:
                print(f"Processing {csv_file.name}...")
                df = pd.read_csv(csv_file)
                
                # Try to standardize and store
                news_df = standardize_kaggle_news(df, dataset_ref)
                
                if not news_df.empty:
                    # Filter by date range
                    if 'timestamp' in news_df.columns:
                        news_df = news_df[
                            (news_df['timestamp'] >= start_date) &
                            (news_df['timestamp'] <= end_date)
                        ]
                    
                    if not news_df.empty:
                        stored = news_engine.store_news(
                            news_df,
                            source=f"kaggle_{dataset_ref.split('/')[-1]}"
                        )
                        print(f"✓ Stored {len(news_df)} news items from {csv_file.name}")
                        total_imported += len(news_df)
                
        except Exception as e:
            print(f"⚠️  Could not process {dataset_ref}: {e}")
            continue
    
    # Final report
    print(f"\n{'=' * 100}")
    print("FINAL REPORT")
    print('=' * 100)
    
    # Query database to verify
    all_news = news_engine.query_news()
    
    print(f"\n✓ Total news items in database: {len(all_news)}")
    print(f"✓ Newly imported: {total_imported}")
    
    if not all_news.empty:
        print(f"\nDate range in database:")
        print(f"  - Earliest: {all_news['timestamp'].min()}")
        print(f"  - Latest: {all_news['timestamp'].max()}")
        
        print(f"\nSources in database:")
        source_counts = all_news['source'].value_counts()
        for source, count in source_counts.head(20).items():
            print(f"  - {source}: {count} articles")
        
        print(f"\nCategories in database:")
        if 'category' in all_news.columns:
            cat_counts = all_news['category'].value_counts()
            for cat, count in cat_counts.head(10).items():
                print(f"  - {cat}: {count} articles")
    
    print(f"\n{'=' * 100}")
    print("✓ Historical data population completed!")
    print('=' * 100)

def prepare_dataset_for_storage(df: pd.DataFrame, dataset_info: dict,
                                start_date: datetime, end_date: datetime,
                                source_name: str) -> pd.DataFrame:
    """Prepare a dataset for storage in NewsEngine format"""
    
    news_items = []
    
    for idx, row in df.iterrows():
        # Extract text
        text = row.get(dataset_info.get('text_column', 'text'), '')
        title = row.get(dataset_info.get('title_column', 'title'), text[:100])
        
        if not text or len(text) < 50:
            continue
        
        # Check if relevant to our tracked assets
        text_upper = text.upper()
        is_crypto = any(crypto in text_upper for crypto in MAJOR_CRYPTOS)
        is_stock = any(stock in text_upper for stock in MAJOR_STOCKS)
        
        if not (is_crypto or is_stock):
            continue
        
        # Create news item
        news_item = {
            'title': title,
            'link': f"huggingface://{source_name}/{idx}",
            'timestamp': datetime.now(timezone.utc),  # Use current time for historical data
            'source': source_name,
            'category': 'news',
            'summary': text[:500],
            'content': text,
            'tags': ''
        }
        
        # Add sentiment if available
        if 'sentiment_column' in dataset_info:
            sentiment = row.get(dataset_info['sentiment_column'], '')
            news_item['tags'] = f"sentiment:{sentiment}"
        
        news_items.append(news_item)
    
    return pd.DataFrame(news_items)

def standardize_kaggle_news(df: pd.DataFrame, dataset_ref: str) -> pd.DataFrame:
    """Standardize Kaggle news dataset to NewsEngine format"""
    
    # Try to identify columns
    text_cols = ['text', 'content', 'article', 'body', 'description', 'headline', 'news']
    title_cols = ['title', 'headline', 'subject']
    date_cols = ['date', 'timestamp', 'published', 'pub_date', 'time']
    
    text_col = None
    title_col = None
    date_col = None
    
    # Find matching columns (case-insensitive)
    df_cols_lower = {col.lower(): col for col in df.columns}
    
    for col in text_cols:
        if col in df_cols_lower:
            text_col = df_cols_lower[col]
            break
    
    for col in title_cols:
        if col in df_cols_lower:
            title_col = df_cols_lower[col]
            break
    
    for col in date_cols:
        if col in df_cols_lower:
            date_col = df_cols_lower[col]
            break
    
    if not text_col:
        print(f"⚠️  Could not identify text column in {dataset_ref}")
        return pd.DataFrame()
    
    news_items = []
    
    for idx, row in df.iterrows():
        text = str(row.get(text_col, ''))
        title = str(row.get(title_col, text[:100]) if title_col else text[:100])
        
        if len(text) < 50:
            continue
        
        # Check relevance
        text_upper = text.upper()
        is_crypto = any(crypto in text_upper for crypto in MAJOR_CRYPTOS)
        is_stock = any(stock in text_upper for stock in MAJOR_STOCKS)
        
        if not (is_crypto or is_stock):
            continue
        
        # Parse date if available
        timestamp = datetime.now(timezone.utc)
        if date_col:
            try:
                timestamp = pd.to_datetime(row[date_col])
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except:
                pass
        
        news_item = {
            'title': title,
            'link': f"kaggle://{dataset_ref}/{idx}",
            'timestamp': timestamp,
            'source': f"kaggle_{dataset_ref.split('/')[-1]}",
            'category': 'news',
            'summary': text[:500],
            'content': text,
            'tags': ''
        }
        
        news_items.append(news_item)
    
    return pd.DataFrame(news_items)

if __name__ == "__main__":
    populate_historical_news()
