#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# RealtimeAlertManager: Gerador de sinais de trading baseado em sentiment
# - Lê news_sentiment e news_by_symbol
# - Aplica thresholds configuráveis (sentiment_score, confidence)
# - Gera sinais em realtime_alerts (status='active')
# - Usa estratégia champion: sentiment_score > 0.2 AND confidence > 0.8
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import hashlib

from engines.smart_db import SmartDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RealtimeAlertManager:
    """
    Gerador de sinais de trading baseado em análise de sentiment.
    
    Responsabilidades:
    1. Carregar news_sentiment e news_by_symbol recentes
    2. Aplicar thresholds (baseado em backtest champion)
    3. Detectar sinais de alta confiança
    4. Gerar alertas em realtime_alerts (status='active')
    5. Deduplicar sinais (evitar múltiplos alertas por símbolo/período)
    
    Estratégia Champion (4h timeframe):
    - sentiment_score > 0.2 (positivo) OR < -0.2 (negativo)
    - confidence > 0.8 (alta confiança)
    - Sharpe: 5.09, Return: 1319%, Win Rate: 17.1%
    """
    
    # Default thresholds from champion strategy
    DEFAULT_CONFIG = {
        'thresholds': {
            'min_sentiment_score': 0.2,      # |score| > 0.2
            'min_confidence': 0.8,            # confidence > 0.8
            'min_news_age_minutes': 5,       # Ignore news < 5min old (avoid noise)
            'max_news_age_hours': 24,        # Ignore news > 24h old
        },
        'signal_settings': {
            'lookback_hours': 4,              # Check last 4h of news (champion timeframe)
            'min_signal_strength': 0.5,      # Combined metric threshold
            'deduplicate_window_hours': 2,   # Avoid duplicate signals within 2h
        },
        'symbols': {
            'stocks': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'META', 'AMZN'],
            'crypto': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT']
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize RealtimeAlertManager.
        
        Args:
            config_path: Optional path to custom config JSON
        """
        # Load config
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = self.DEFAULT_CONFIG
        
        self.db = SmartDatabaseManager()
        
        logger.info("RealtimeAlertManager initialized")
        logger.info(f"Thresholds: score>{self.config['thresholds']['min_sentiment_score']}, "
                   f"conf>{self.config['thresholds']['min_confidence']}")
    
    def run(self):
        """
        Execute alert generation pipeline.
        
        Process:
        1. Load recent news sentiment
        2. Load per-symbol sentiment
        3. Aggregate sentiment signals
        4. Apply thresholds
        5. Generate alerts
        6. Deduplicate
        7. Save to realtime_alerts
        """
        logger.info("=== RealtimeAlertManager.run() ===")
        
        # 1. Load recent sentiment data
        general_sentiment = self._load_general_sentiment()
        symbol_sentiment = self._load_symbol_sentiment()
        
        if general_sentiment.empty and symbol_sentiment.empty:
            logger.info("No recent sentiment data to process")
            return
        
        logger.info(f"Loaded {len(general_sentiment)} general + {len(symbol_sentiment)} symbol sentiments")
        
        # 2. Generate signals from symbol-specific sentiment (primary)
        symbol_signals = self._generate_symbol_signals(symbol_sentiment)
        
        # 3. Generate signals from general sentiment (fallback)
        general_signals = self._generate_general_signals(general_sentiment)
        
        # 4. Combine and deduplicate
        all_signals = pd.concat([symbol_signals, general_signals], ignore_index=True)
        
        if all_signals.empty:
            logger.info("No signals generated")
            return
        
        logger.info(f"Generated {len(all_signals)} candidate signals")
        
        # 5. Deduplicate (prefer symbol-specific over general)
        deduplicated = self._deduplicate_signals(all_signals)
        logger.info(f"After deduplication: {len(deduplicated)} signals")
        
        # 6. Save to realtime_alerts
        self._save_alerts(deduplicated)
        
        logger.info(f"Pipeline complete: {len(deduplicated)} new alerts created")
    
    def _load_general_sentiment(self) -> pd.DataFrame:
        """Load recent general sentiment"""
        lookback = self.config['signal_settings']['lookback_hours']
        cutoff = datetime.now() - timedelta(hours=lookback)
        
        query = f"""
        SELECT 
            news_id,
            timestamp,
            source,
            title,
            sentiment,
            sentiment_score,
            confidence,
            analyzed_at
        FROM news_sentiment
        WHERE timestamp >= '{cutoff.isoformat()}'
        AND analyzed_at >= '{cutoff.isoformat()}'
        ORDER BY timestamp DESC
        """
        
        try:
            return self.db.query(query)
        except Exception as e:
            logger.warning(f"Error loading general sentiment: {e}")
            return pd.DataFrame()
    
    def _load_symbol_sentiment(self) -> pd.DataFrame:
        """Load recent per-symbol sentiment"""
        lookback = self.config['signal_settings']['lookback_hours']
        cutoff = datetime.now() - timedelta(hours=lookback)
        
        # Get watchlist
        watchlist = (self.config['symbols']['stocks'] + 
                    self.config['symbols']['crypto'])
        
        if not watchlist:
            return pd.DataFrame()
        
        symbols_str = "', '".join(watchlist)
        
        query = f"""
        SELECT 
            news_id,
            symbol,
            timestamp,
            source,
            title,
            sentiment,
            sentiment_score,
            confidence,
            matched_sentence,
            analyzed_at
        FROM news_by_symbol
        WHERE timestamp >= '{cutoff.isoformat()}'
        AND analyzed_at >= '{cutoff.isoformat()}'
        AND symbol IN ('{symbols_str}')
        ORDER BY timestamp DESC
        """
        
        try:
            return self.db.query(query)
        except Exception as e:
            logger.warning(f"Error loading symbol sentiment: {e}")
            return pd.DataFrame()
    
    def _generate_symbol_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals from per-symbol sentiment"""
        if df.empty:
            return pd.DataFrame()
        
        thresholds = self.config['thresholds']
        
        # Apply filters
        df = df[
            (abs(df['sentiment_score']) > thresholds['min_sentiment_score']) &
            (df['confidence'] > thresholds['min_confidence'])
        ]
        
        if df.empty:
            return pd.DataFrame()
        
        # Aggregate by symbol (multiple news → single signal)
        signals = []
        
        for symbol, group in df.groupby('symbol'):
            # Use most recent high-confidence sentiment
            group = group.sort_values('timestamp', ascending=False)
            latest = group.iloc[0]
            
            # Calculate signal strength (weighted by confidence)
            signal_strength = abs(latest['sentiment_score']) * latest['confidence']
            
            if signal_strength < self.config['signal_settings']['min_signal_strength']:
                continue
            
            # Determine signal type
            if latest['sentiment_score'] > 0:
                signal_type = 'buy'
            else:
                signal_type = 'sell'
            
            signal = {
                'symbol': symbol,
                'signal_type': signal_type,
                'signal_strength': signal_strength,
                'sentiment_score': latest['sentiment_score'],
                'confidence': latest['confidence'],
                'news_count': len(group),
                'latest_news_id': latest['news_id'],
                'news_ids': ','.join(group['news_id'].astype(str).tolist()[:5]),  # Top 5
                'source': 'symbol_sentiment',
                'timestamp': latest['timestamp'],
                'title': latest['title'],
                'matched_sentence': latest.get('matched_sentence', '')
            }
            
            signals.append(signal)
        
        return pd.DataFrame(signals)
    
    def _generate_general_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate signals from general sentiment (for symbols not in watchlist)"""
        if df.empty:
            return pd.DataFrame()
        
        thresholds = self.config['thresholds']
        
        # Apply filters
        df = df[
            (abs(df['sentiment_score']) > thresholds['min_sentiment_score']) &
            (df['confidence'] > thresholds['min_confidence'])
        ]
        
        if df.empty:
            return pd.DataFrame()
        
        # TODO: Extract symbols from title (simple regex)
        # For now, skip general signals
        # In production, you'd extract tickers and create signals
        
        return pd.DataFrame()
    
    def _deduplicate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Deduplicate signals to avoid multiple alerts for same symbol"""
        if df.empty:
            return df
        
        # Check existing active alerts
        dedup_window = self.config['signal_settings']['deduplicate_window_hours']
        cutoff = datetime.now() - timedelta(hours=dedup_window)
        
        query = f"""
        SELECT DISTINCT symbol
        FROM realtime_alerts
        WHERE status = 'active'
        AND timestamp >= '{cutoff.isoformat()}'
        """
        
        try:
            existing = self.db.query(query)
            if not existing.empty:
                existing_symbols = set(existing['symbol'].tolist())
                
                # Filter out symbols with recent active alerts
                df = df[~df['symbol'].isin(existing_symbols)]
                
                if len(existing_symbols) > 0:
                    logger.info(f"Filtered {len(existing_symbols)} symbols with recent alerts")
        except Exception as e:
            logger.warning(f"Could not check existing alerts: {e}")
        
        # Also deduplicate within current batch (keep strongest signal per symbol)
        df = df.sort_values('signal_strength', ascending=False)
        df = df.drop_duplicates(subset=['symbol'], keep='first')
        
        return df
    
    def _save_alerts(self, df: pd.DataFrame):
        """Save alerts to realtime_alerts table"""
        if df.empty:
            return
        
        # Add metadata
        now = datetime.now()
        
        # Generate unique IDs
        df['id'] = df.apply(
            lambda row: f"alert_{row['symbol']}_{now.strftime('%Y%m%d%H%M%S')}_{hashlib.md5(str(row['news_ids']).encode()).hexdigest()[:8]}",
            axis=1
        )
        
        df['status'] = 'active'
        df['created_at'] = now
        df['price'] = 0.0  # TODO: Fetch current price from AutoFetchData/Connector
        
        # Reorder columns for database
        columns = [
            'id', 'symbol', 'signal_type', 'signal_strength',
            'sentiment_score', 'confidence', 'price',
            'timestamp', 'status', 'created_at',
            'news_count', 'news_ids', 'source', 'title'
        ]
        
        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = ''
        
        df = df[columns]
        
        # Save to database
        try:
            self.db.save_dataframe(df, 'realtime_alerts', mode='append')
            logger.info(f"Saved {len(df)} new alerts")
            
            # Log summary
            for _, row in df.iterrows():
                logger.info(f"  → {row['signal_type'].upper()} {row['symbol']}: "
                          f"strength={row['signal_strength']:.2f}, "
                          f"score={row['sentiment_score']:.2f}, "
                          f"conf={row['confidence']:.2f}")
                          
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")


def main():
    """Test execution"""
    manager = RealtimeAlertManager()
    manager.run()


if __name__ == '__main__':
    main()
