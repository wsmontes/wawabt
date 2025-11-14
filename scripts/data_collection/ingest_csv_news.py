#!/usr/bin/env python3
"""
Ingest CSV news data into the database
Supports Cointelegraph news and other CSV formats
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import Optional

sys.path.insert(0, os.path.abspath('.'))

from engines.smart_db import SmartDatabaseManager


class CSVNewsIngestor:
    """Ingest news data from CSV files into the database"""
    
    def __init__(self):
        self.smart_db = SmartDatabaseManager()
        self.stats = {
            'files_processed': 0,
            'total_records': 0,
            'successfully_saved': 0,
            'failed': 0,
            'errors': []
        }
    
    def ingest_cointelegraph(self, csv_path: str) -> bool:
        """
        Ingest Cointelegraph news CSV
        
        Expected columns: 
        - head.csv: title, lead/leadfull, url, date, category_title, author_title
        - content.csv: id, header, date, content
        """
        print(f"📰 Ingesting Cointelegraph data from: {csv_path}")
        
        try:
            # Load CSV with proper quoting for content fields
            df = pd.read_csv(csv_path, quotechar='"', escapechar='\\', on_bad_lines='skip')
            print(f"   Loaded {len(df)} records")
            
            # Map columns to our schema
            news_df = pd.DataFrame()
            
            # Detect if this is head.csv or content.csv
            is_content_format = 'header' in df.columns and 'content' in df.columns
            
            # Parse timestamp from 'published_date' or 'publishedW3'
            if 'publishedW3' in df.columns:
                news_df['timestamp'] = pd.to_datetime(df['publishedW3'], utc=True)
            elif 'published_date' in df.columns:
                news_df['timestamp'] = pd.to_datetime(df['published_date'], utc=True)
            elif 'date' in df.columns:
                news_df['timestamp'] = pd.to_datetime(df['date'], utc=True)
            else:
                print("   ❌ No date column found")
                return False
            
            # Required fields
            news_df['source'] = 'Cointelegraph_Content' if is_content_format else 'Cointelegraph'
            
            if is_content_format:
                # content.csv format
                news_df['category'] = 'crypto'
                news_df['title'] = df['header']
                news_df['link'] = 'https://cointelegraph.com/news/' + df['id'].astype(str)  # Reconstruct URL
                news_df['description'] = df.get('content', '')
            else:
                # head.csv format
                news_df['category'] = df.get('category_title', 'crypto')
                news_df['title'] = df['title']
                news_df['link'] = df['url']
                news_df['description'] = df.get('lead', df.get('leadfull', ''))
            
            # Optional fields
            news_df['author'] = df.get('author_title', '')
            news_df['tags'] = None  # Could parse from category
            
            # Filter out records with invalid timestamps
            news_df = news_df.dropna(subset=['timestamp'])
            
            # Filter out very old or future dates (data quality check)
            min_date = pd.Timestamp('2015-01-01', tz='UTC')
            max_date = pd.Timestamp.now(tz='UTC')
            news_df = news_df[(news_df['timestamp'] >= min_date) & (news_df['timestamp'] <= max_date)]
            
            print(f"   Valid records after filtering: {len(news_df)}")
            
            if len(news_df) == 0:
                print("   ⚠️  No valid records to ingest")
                return False
            
            # Save to database
            saved_files = self.smart_db.store_news_data(news_df, source='Cointelegraph')
            
            self.stats['files_processed'] += 1
            self.stats['total_records'] += len(df)
            self.stats['successfully_saved'] += len(news_df)
            
            print(f"   ✅ Successfully ingested {len(news_df)} records")
            print(f"   📁 Saved to {len(saved_files)} file(s)")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.stats['failed'] += 1
            self.stats['errors'].append({'file': csv_path, 'error': str(e)})
            import traceback
            traceback.print_exc()
            return False
    
    def ingest_generic_news(self, csv_path: str, source_name: str,
                           title_col: str = 'title',
                           date_col: str = 'date',
                           url_col: str = 'url',
                           description_col: Optional[str] = None,
                           category_col: Optional[str] = None,
                           author_col: Optional[str] = None) -> bool:
        """
        Ingest generic news CSV with custom column mapping
        """
        print(f"📰 Ingesting {source_name} data from: {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
            print(f"   Loaded {len(df)} records")
            
            # Map columns
            news_df = pd.DataFrame()
            
            # Required fields
            news_df['timestamp'] = pd.to_datetime(df[date_col], utc=True)
            news_df['source'] = source_name
            news_df['title'] = df[title_col]
            news_df['link'] = df[url_col]
            
            # Optional fields
            news_df['category'] = df[category_col] if category_col and category_col in df.columns else 'general'
            news_df['description'] = df[description_col] if description_col and description_col in df.columns else ''
            news_df['author'] = df[author_col] if author_col and author_col in df.columns else ''
            news_df['tags'] = None
            
            # Filter invalid data
            news_df = news_df.dropna(subset=['timestamp', 'title', 'link'])
            
            min_date = pd.Timestamp('2015-01-01', tz='UTC')
            max_date = pd.Timestamp.now(tz='UTC')
            news_df = news_df[(news_df['timestamp'] >= min_date) & (news_df['timestamp'] <= max_date)]
            
            print(f"   Valid records after filtering: {len(news_df)}")
            
            if len(news_df) == 0:
                print("   ⚠️  No valid records to ingest")
                return False
            
            # Save to database
            saved_files = self.smart_db.store_news_data(news_df, source=source_name)
            
            self.stats['files_processed'] += 1
            self.stats['total_records'] += len(df)
            self.stats['successfully_saved'] += len(news_df)
            
            print(f"   ✅ Successfully ingested {len(news_df)} records")
            print(f"   📁 Saved to {len(saved_files)} file(s)")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.stats['failed'] += 1
            self.stats['errors'].append({'file': csv_path, 'error': str(e)})
            import traceback
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """Print ingestion summary"""
        print("\n" + "="*70)
        print(" INGESTION SUMMARY")
        print("="*70)
        
        print(f"\n📊 Statistics:")
        print(f"   Files processed:  {self.stats['files_processed']}")
        print(f"   Total records:    {self.stats['total_records']}")
        print(f"   Successfully saved: {self.stats['successfully_saved']}")
        print(f"   Failed:           {self.stats['failed']}")
        
        if self.stats['errors']:
            print(f"\n❌ Errors:")
            for error in self.stats['errors']:
                print(f"   • {error['file']}: {error['error'][:100]}")
        
        # Database status
        try:
            all_data = self.smart_db.query_news_data()
            print(f"\n💾 Database Status:")
            print(f"   Total records in DB: {len(all_data)}")
            
            if not all_data.empty:
                sources = all_data['source'].value_counts()
                print(f"   Unique sources: {len(sources)}")
                
                if 'Cointelegraph' in sources.index:
                    print(f"   Cointelegraph records: {sources['Cointelegraph']}")
        except Exception as e:
            print(f"   ⚠️  Could not query database: {e}")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest news data from CSV files')
    parser.add_argument('files', nargs='+', help='CSV file(s) to ingest')
    parser.add_argument('--source', default='Cointelegraph',
                       help='Source name (default: Cointelegraph)')
    parser.add_argument('--auto-detect', action='store_true',
                       help='Auto-detect source from filename')
    parser.add_argument('--title-col', default='title',
                       help='Title column name (default: title)')
    parser.add_argument('--date-col', default='date',
                       help='Date column name (default: date)')
    parser.add_argument('--url-col', default='url',
                       help='URL column name (default: url)')
    parser.add_argument('--description-col', default=None,
                       help='Description column name (optional)')
    parser.add_argument('--category-col', default=None,
                       help='Category column name (optional)')
    parser.add_argument('--author-col', default=None,
                       help='Author column name (optional)')
    
    args = parser.parse_args()
    
    ingestor = CSVNewsIngestor()
    
    print("="*70)
    print(" CSV NEWS INGESTOR")
    print("="*70)
    print()
    
    for file_path in args.files:
        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            continue
        
        # Detect source from filename
        source = args.source
        if args.auto_detect:
            filename = Path(file_path).stem.lower()
            if 'cointelegraph' in filename:
                source = 'Cointelegraph'
            elif 'quandl' in filename:
                source = 'Quandl'
            else:
                source = Path(file_path).stem
        
        # Try Cointelegraph format first
        if 'cointelegraph' in source.lower():
            success = ingestor.ingest_cointelegraph(file_path)
        else:
            # Use generic format
            success = ingestor.ingest_generic_news(
                file_path,
                source_name=source,
                title_col=args.title_col,
                date_col=args.date_col,
                url_col=args.url_col,
                description_col=args.description_col,
                category_col=args.category_col,
                author_col=args.author_col
            )
    
    ingestor.print_summary()
    
    if ingestor.stats['successfully_saved'] > 0:
        print("\n✅ Ingestion completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ No records were successfully ingested")
        sys.exit(1)


if __name__ == "__main__":
    main()
