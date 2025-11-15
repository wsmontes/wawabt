#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# SentimentAnalysisPipeline: Orquestrador de análise de sentimento
# - Load news_raw com status='pending'
# - Usa FinBERTEngine.analyze_news_df() para batch processing
# - Usa FinBERTEngine.analyze_per_symbol() para análise por símbolo
# - Save em news_sentiment e news_by_symbol
# - Update news_raw status='processed'
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
from datetime import datetime
from typing import Optional
import pandas as pd

from engines.finbert import FinBERTEngine
from engines.smart_db import SmartDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SentimentAnalysisPipeline:
    """
    Pipeline orquestrador para análise de sentimento em notícias.
    
    Responsabilidades:
    1. Carregar news_raw com status='pending'
    2. Processar em batch com FinBERTEngine
    3. Análise geral (title + description)
    4. Análise per-symbol (para cada ticker mencionado)
    5. Salvar em news_sentiment (análise geral)
    6. Salvar em news_by_symbol (análise específica)
    7. Atualizar news_raw status='processed'
    
    NÃO duplica código - apenas orquestra FinBERTEngine existente.
    """
    
    def __init__(self, device: str = 'cpu', batch_size: int = 16):
        """
        Initialize SentimentAnalysisPipeline.
        
        Args:
            device: 'cpu' or 'cuda' for GPU acceleration
            batch_size: Batch size for processing (larger = faster but more RAM)
        """
        self.batch_size = batch_size
        
        # Initialize engines (reuse existing)
        logger.info("Initializing FinBERT engine...")
        
        self.finbert = FinBERTEngine(
            use_smart_db=True,
            device=device
        )
        
        self.db = SmartDatabaseManager()
        
        logger.info("SentimentAnalysisPipeline initialized")
    
    def run(self, limit: Optional[int] = None):
        """
        Execute pipeline: analyze pending news.
        
        Args:
            limit: Optional limit of articles to process (for testing)
        """
        logger.info("=== SentimentAnalysisPipeline.run() ===")
        
        # 1. Load pending news
        pending_news = self._load_pending_news(limit)
        
        if pending_news.empty:
            logger.info("No pending news to analyze")
            return
        
        logger.info(f"Processing {len(pending_news)} pending articles")
        
        # 2. Analyze general sentiment (uses FinBERTEngine.analyze_news_df)
        analyzed = self.finbert.analyze_news_df(
            pending_news,
            text_column='title',
            description_column='description'
        )
        
        # 3. Calculate composite sentiment score
        analyzed = self._calculate_sentiment_score(analyzed)
        
        # 4. Save general sentiment
        self._save_general_sentiment(analyzed)
        
        # 5. Analyze per-symbol sentiment
        self._analyze_per_symbol(analyzed)
        
        # 6. Update status to 'processed'
        self._update_status(analyzed['id'].tolist())
        
        logger.info(f"Pipeline complete: {len(analyzed)} articles analyzed")
    
    def _load_pending_news(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Load news with status='pending' from news_raw"""
        query = """
        SELECT 
            id,
            timestamp,
            title,
            description,
            link,
            source,
            category,
            tickers_mentioned,
            cryptos_mentioned,
            content_hash
        FROM news_raw
        WHERE status = 'pending'
        ORDER BY timestamp DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        df = self.db.query(query)
        
        logger.info(f"Loaded {len(df)} pending articles")
        return df
    
    def _calculate_sentiment_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate composite sentiment score.
        
        Score formula:
        - positive: +1 * confidence
        - negative: -1 * confidence
        - neutral: 0
        
        Range: -1.0 (very negative) to +1.0 (very positive)
        """
        def calc_score(row):
            if row['sentiment'] == 'positive':
                return row['sentiment_confidence']
            elif row['sentiment'] == 'negative':
                return -row['sentiment_confidence']
            else:  # neutral
                return 0.0
        
        df['sentiment_score'] = df.apply(calc_score, axis=1)
        
        return df
    
    def _save_general_sentiment(self, df: pd.DataFrame):
        """Save general sentiment analysis to news_sentiment table"""
        # Prepare data
        sentiment_df = pd.DataFrame()
        sentiment_df['id'] = 'sentiment_' + df['id']
        sentiment_df['news_id'] = df['id']
        sentiment_df['timestamp'] = df['timestamp']
        sentiment_df['source'] = df['source']
        sentiment_df['title'] = df['title']
        sentiment_df['link'] = df['link']
        sentiment_df['sentiment'] = df['sentiment']
        sentiment_df['sentiment_score'] = df['sentiment_score']
        sentiment_df['confidence'] = df['sentiment_confidence']
        sentiment_df['positive_score'] = df['sentiment_positive']
        sentiment_df['negative_score'] = df['sentiment_negative']
        sentiment_df['neutral_score'] = df['sentiment_neutral']
        sentiment_df['analyzed_at'] = datetime.now()
        
        # Save to database
        try:
            self.db.save_dataframe(sentiment_df, 'news_sentiment', mode='append')
            logger.info(f"Saved {len(sentiment_df)} general sentiment analyses")
        except Exception as e:
            logger.error(f"Error saving general sentiment: {e}")
    
    def _analyze_per_symbol(self, df: pd.DataFrame):
        """Analyze sentiment per symbol mentioned"""
        symbol_results = []
        
        for _, row in df.iterrows():
            # Get all symbols mentioned
            tickers = row.get('tickers_mentioned', '')
            cryptos = row.get('cryptos_mentioned', '')
            
            # Combine and clean
            symbols = []
            if tickers:
                symbols.extend([s.strip() for s in str(tickers).split(',') if s.strip()])
            if cryptos:
                symbols.extend([s.strip() for s in str(cryptos).split(',') if s.strip()])
            
            if not symbols:
                continue
            
            # Combine title + description for context
            full_text = f"{row['title']} {row.get('description', '')}"
            
            # Analyze per symbol (uses FinBERTEngine.analyze_per_symbol)
            try:
                symbol_sentiments = self.finbert.analyze_per_symbol(full_text, symbols)
                
                for symbol, sentiment_data in symbol_sentiments.items():
                    result = {
                        'id': f"symbol_{row['id']}_{symbol}",
                        'news_id': row['id'],
                        'symbol': symbol,
                        'timestamp': row['timestamp'],
                        'source': row['source'],
                        'title': row['title'],
                        'sentiment': sentiment_data['sentiment'],
                        'sentiment_score': (
                            sentiment_data['confidence'] if sentiment_data['sentiment'] == 'positive'
                            else -sentiment_data['confidence'] if sentiment_data['sentiment'] == 'negative'
                            else 0.0
                        ),
                        'confidence': sentiment_data['confidence'],
                        'positive_score': sentiment_data['scores']['positive'],
                        'negative_score': sentiment_data['scores']['negative'],
                        'neutral_score': sentiment_data['scores']['neutral'],
                        'matched_sentence': sentiment_data.get('matched_sentence', ''),
                        'analyzed_at': datetime.now()
                    }
                    symbol_results.append(result)
                    
            except Exception as e:
                logger.warning(f"Error analyzing per-symbol for {row['id']}: {e}")
                continue
        
        # Save per-symbol results
        if symbol_results:
            symbol_df = pd.DataFrame(symbol_results)
            
            try:
                self.db.save_dataframe(symbol_df, 'news_by_symbol', mode='append')
                logger.info(f"Saved {len(symbol_df)} per-symbol sentiment analyses")
            except Exception as e:
                logger.error(f"Error saving per-symbol sentiment: {e}")
        else:
            logger.info("No symbol-specific analyses to save")
    
    def _update_status(self, news_ids: list):
        """Update news_raw status to 'processed'"""
        if not news_ids:
            return
        
        # Build update query
        ids_str = "', '".join(news_ids)
        query = f"""
        UPDATE news_raw
        SET status = 'processed',
            processed_at = '{datetime.now().isoformat()}'
        WHERE id IN ('{ids_str}')
        """
        
        try:
            self.db.execute(query)
            logger.info(f"Updated {len(news_ids)} articles to 'processed' status")
        except Exception as e:
            logger.error(f"Error updating status: {e}")


def main():
    """Test execution"""
    # Use CPU for testing (change to 'cuda' if GPU available)
    pipeline = SentimentAnalysisPipeline(device='cpu', batch_size=16)
    
    # Process max 100 articles for testing
    pipeline.run(limit=100)


if __name__ == '__main__':
    main()
