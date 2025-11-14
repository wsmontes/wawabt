#!/usr/bin/env python3
"""
FinBERT Sentiment Analysis Engine
Analyzes financial news sentiment using FinBERT model
Saves results to database via SmartDatabaseManager
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Union
import pandas as pd
import numpy as np
import logging

sys.path.insert(0, os.path.abspath('.'))

from engines.smart_db import SmartDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('FinBERT')


class FinBERTEngine:
    """
    Financial Sentiment Analysis using FinBERT
    
    FinBERT is a pre-trained NLP model to analyze sentiment of financial text.
    It is built by further training the BERT language model on financial communication.
    
    Sentiment classes:
    - positive: optimistic, bullish
    - negative: pessimistic, bearish  
    - neutral: factual, no clear sentiment
    """
    
    def __init__(self, use_smart_db: bool = True, device: str = 'cpu'):
        """
        Initialize FinBERT engine
        
        Args:
            use_smart_db: Whether to use SmartDatabaseManager for storage
            device: 'cpu' or 'cuda' for GPU acceleration
        """
        self.use_smart_db = use_smart_db
        self.device = device
        self.model = None
        self.tokenizer = None
        self.smart_db = None
        
        if self.use_smart_db:
            self.smart_db = SmartDatabaseManager()
            logger.info("Smart Database integration enabled")
        
        self._load_model()
    
    def _load_model(self):
        """Load FinBERT model and tokenizer"""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            logger.info("Loading FinBERT model...")
            
            model_name = "ProsusAI/finbert"
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            
            # Move model to device
            if self.device == 'cuda' and torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("FinBERT model loaded on GPU")
            else:
                self.model = self.model.cpu()
                logger.info("FinBERT model loaded on CPU")
            
            self.model.eval()  # Set to evaluation mode
            
        except ImportError as e:
            logger.error(f"Failed to import transformers: {e}")
            logger.error("Install with: pip install transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            raise
    
    def analyze_sentiment(self, text: str) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """
        Analyze sentiment of a single text
        
        Args:
            text: Financial text to analyze
            
        Returns:
            Dictionary with sentiment analysis results:
            {
                'sentiment': 'positive' | 'negative' | 'neutral',
                'confidence': float (0-1),
                'scores': {
                    'positive': float,
                    'negative': float,
                    'neutral': float
                }
            }
        """
        if not text or not isinstance(text, str):
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'scores': {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0}
            }
        
        try:
            import torch
            
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Move to device
            if self.device == 'cuda':
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # Convert to numpy
            predictions = predictions.cpu().numpy()[0]
            
            # Labels: positive (0), negative (1), neutral (2) - from model config
            labels = ['positive', 'negative', 'neutral']
            scores = {label: float(score) for label, score in zip(labels, predictions)}
            
            # Get dominant sentiment
            sentiment = max(scores, key=scores.get)
            confidence = scores[sentiment]
            
            return {
                'sentiment': sentiment,
                'confidence': confidence,
                'scores': scores
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {
                'sentiment': 'neutral',
                'confidence': 0.0,
                'scores': {'positive': 0.0, 'negative': 0.0, 'neutral': 1.0},
                'error': str(e)
            }
    
    def analyze_batch(self, texts: List[str], batch_size: int = 16) -> List[Dict]:
        """
        Analyze sentiment of multiple texts in batches
        
        Args:
            texts: List of texts to analyze
            batch_size: Number of texts to process at once
            
        Returns:
            List of sentiment analysis results
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            for text in batch:
                result = self.analyze_sentiment(text)
                results.append(result)
            
            if (i + batch_size) % 100 == 0:
                logger.info(f"Processed {i + batch_size}/{len(texts)} texts")
        
        return results
    
    def analyze_news_df(self, news_df: pd.DataFrame, 
                        text_column: str = 'title',
                        description_column: Optional[str] = 'description') -> pd.DataFrame:
        """
        Analyze sentiment of news DataFrame
        
        Args:
            news_df: DataFrame with news data
            text_column: Column name containing the main text (default: 'title')
            description_column: Optional column for additional text context
            
        Returns:
            DataFrame with added sentiment columns
        """
        logger.info(f"Analyzing sentiment for {len(news_df)} news articles")
        
        # Combine title and description if available
        if description_column and description_column in news_df.columns:
            texts = (news_df[text_column].fillna('') + ' ' + 
                    news_df[description_column].fillna('')).tolist()
        else:
            texts = news_df[text_column].fillna('').tolist()
        
        # Analyze sentiments
        sentiments = self.analyze_batch(texts)
        
        # Add results to dataframe
        result_df = news_df.copy()
        result_df['sentiment'] = [s['sentiment'] for s in sentiments]
        result_df['sentiment_confidence'] = [s['confidence'] for s in sentiments]
        result_df['sentiment_positive'] = [s['scores']['positive'] for s in sentiments]
        result_df['sentiment_negative'] = [s['scores']['negative'] for s in sentiments]
        result_df['sentiment_neutral'] = [s['scores']['neutral'] for s in sentiments]
        result_df['analyzed_at'] = datetime.now()
        
        logger.info(f"Sentiment analysis completed")
        logger.info(f"  Positive: {(result_df['sentiment'] == 'positive').sum()}")
        logger.info(f"  Negative: {(result_df['sentiment'] == 'negative').sum()}")
        logger.info(f"  Neutral: {(result_df['sentiment'] == 'neutral').sum()}")
        
        return result_df
    
    def analyze_per_symbol(self, text: str, symbols: List[str]) -> Dict[str, Dict]:
        """
        Analyze sentiment for each symbol mentioned in text
        
        Extracts sentences mentioning each symbol and analyzes the one
        with highest confidence (clearest sentiment signal).
        
        Args:
            text: Full article text (title + description + content)
            symbols: List of symbols mentioned in the article
            
        Returns:
            Dict mapping symbol to sentiment analysis result
        """
        if not text or not symbols:
            return {}
        
        import re
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        symbol_sentiments = {}
        
        for symbol in symbols:
            # Find sentences mentioning this symbol
            # Check for symbol itself and common variations
            symbol_patterns = [
                symbol,  # Exact match
                symbol.replace('USDT', ''),  # Crypto without USDT
                f"${symbol}",  # With dollar sign
            ]
            
            relevant_sentences = []
            for sentence in sentences:
                sentence_upper = sentence.upper()
                if any(pattern.upper() in sentence_upper for pattern in symbol_patterns):
                    relevant_sentences.append(sentence)
            
            if not relevant_sentences:
                # Symbol mentioned but no clear sentence - use full text
                result = self.analyze_sentiment(text)
                symbol_sentiments[symbol] = result
                continue
            
            # Analyze all relevant sentences
            best_result = None
            max_confidence = 0
            
            for sentence in relevant_sentences:
                try:
                    result = self.analyze_sentiment(sentence)
                    
                    # Track the sentence with highest confidence
                    if result['confidence'] > max_confidence:
                        max_confidence = result['confidence']
                        best_result = result
                        best_result['matched_sentence'] = sentence
                
                except Exception as e:
                    logger.warning(f"Error analyzing sentence for {symbol}: {e}")
                    continue
            
            if best_result:
                symbol_sentiments[symbol] = best_result
        
        return symbol_sentiments
    
    def analyze_and_save(self, source: Optional[str] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        limit: Optional[int] = None) -> pd.DataFrame:
        """
        Analyze sentiment of news from database and save results
        
        Args:
            source: News source to analyze (None for all)
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            limit: Maximum number of articles to analyze
            
        Returns:
            DataFrame with sentiment analysis results
        """
        if not self.smart_db:
            raise RuntimeError("SmartDatabaseManager not initialized")
        
        # Query news data
        logger.info(f"Querying news data (source={source}, dates={start_date} to {end_date})")
        news_df = self.smart_db.query_news_data(
            source=source,
            start_date=start_date,
            end_date=end_date
        )
        
        if news_df.empty:
            logger.warning("No news data found")
            return pd.DataFrame()
        
        if limit:
            news_df = news_df.head(limit)
        
        logger.info(f"Found {len(news_df)} articles to analyze")
        
        # Analyze sentiment
        result_df = self.analyze_news_df(news_df)
        
        # Save to database
        logger.info("Saving sentiment analysis to database...")
        
        # Prepare data for storage
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
        
        # Extract symbol from source if available (for stock-specific news)
        if 'category' in result_df.columns:
            sentiment_df['category'] = result_df['category']
        
        # Save using analysis_data storage
        saved_files = self.smart_db.store_analysis_data(
            df=sentiment_df,
            analysis_type='sentiment',
            symbol=source if source else 'all_news'
        )
        
        # saved_files is a Path, not a list
        logger.info(f"✓ Saved sentiment analysis to database")
        
        return result_df
    
    def get_sentiment_summary(self, source: Optional[str] = None,
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> Dict:
        """
        Get sentiment summary statistics
        
        Args:
            source: News source filter
            start_date: Start date filter  
            end_date: End date filter
            
        Returns:
            Dictionary with sentiment statistics
        """
        if not self.smart_db:
            raise RuntimeError("SmartDatabaseManager not initialized")
        
        # Query sentiment analysis data
        # For now, query from news and analyze
        news_df = self.smart_db.query_news_data(
            source=source,
            start_date=start_date,
            end_date=end_date
        )
        
        if news_df.empty:
            return {
                'total': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0,
                'avg_confidence': 0.0
            }
        
        # Analyze
        result_df = self.analyze_news_df(news_df)
        
        summary = {
            'total': len(result_df),
            'positive': (result_df['sentiment'] == 'positive').sum(),
            'negative': (result_df['sentiment'] == 'negative').sum(),
            'neutral': (result_df['sentiment'] == 'neutral').sum(),
            'avg_confidence': result_df['sentiment_confidence'].mean(),
            'positive_pct': (result_df['sentiment'] == 'positive').sum() / len(result_df) * 100,
            'negative_pct': (result_df['sentiment'] == 'negative').sum() / len(result_df) * 100,
            'neutral_pct': (result_df['sentiment'] == 'neutral').sum() / len(result_df) * 100,
        }
        
        return summary


def main():
    """Main execution for testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FinBERT Sentiment Analysis Engine')
    parser.add_argument('--text', type=str, help='Analyze a single text')
    parser.add_argument('--source', type=str, help='News source to analyze')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--limit', type=int, help='Limit number of articles')
    parser.add_argument('--summary', action='store_true', help='Show sentiment summary')
    parser.add_argument('--device', type=str, default='cpu', choices=['cpu', 'cuda'],
                       help='Device to use (cpu or cuda)')
    
    args = parser.parse_args()
    
    # Initialize engine
    print("="*70)
    print(" FinBERT SENTIMENT ANALYSIS ENGINE")
    print("="*70)
    print()
    
    engine = FinBERTEngine(device=args.device)
    
    if args.text:
        # Analyze single text
        print(f"Analyzing: {args.text}\n")
        result = engine.analyze_sentiment(args.text)
        
        print(f"Sentiment: {result['sentiment'].upper()}")
        print(f"Confidence: {result['confidence']:.2%}")
        print(f"\nScores:")
        print(f"  Positive: {result['scores']['positive']:.2%}")
        print(f"  Negative: {result['scores']['negative']:.2%}")
        print(f"  Neutral: {result['scores']['neutral']:.2%}")
        
    elif args.summary:
        # Show summary
        summary = engine.get_sentiment_summary(
            source=args.source,
            start_date=args.start_date,
            end_date=args.end_date
        )
        
        print(f"📊 Sentiment Summary")
        print(f"   Total articles: {summary['total']}")
        print(f"   Positive: {summary['positive']} ({summary['positive_pct']:.1f}%)")
        print(f"   Negative: {summary['negative']} ({summary['negative_pct']:.1f}%)")
        print(f"   Neutral: {summary['neutral']} ({summary['neutral_pct']:.1f}%)")
        print(f"   Avg confidence: {summary['avg_confidence']:.2%}")
        
    else:
        # Analyze and save news
        result_df = engine.analyze_and_save(
            source=args.source,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit
        )
        
        if not result_df.empty:
            print(f"\n✅ Analyzed {len(result_df)} articles")
            print(f"   Saved to database")
        else:
            print("\n⚠️  No articles to analyze")


if __name__ == "__main__":
    main()
