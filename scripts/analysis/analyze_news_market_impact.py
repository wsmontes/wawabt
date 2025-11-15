#!/usr/bin/env python3
"""
News-Market Impact Analysis
Comprehensive analysis of news sentiment impact on market prices
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import json
import logging
from typing import Dict, List, Tuple, Optional
import re
from collections import defaultdict

sys.path.insert(0, os.path.abspath('.'))

from engines.smart_db import SmartDatabaseManager
from engines.connector import EnhancedConnectorEngine
from engines.symbol_reference import SymbolReferenceEngine
from engines.finbert import FinBERTEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('news_market_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NewsMarketAnalyzer:
    """Analyze correlation between news and market movements"""
    
    def __init__(self, lookback_hours: List[int] = [1, 4, 24, 48, 168]):
        """
        Initialize analyzer
        
        Args:
            lookback_hours: Time windows to analyze impact (hours after news)
        """
        self.smart_db = SmartDatabaseManager()
        self.connector = EnhancedConnectorEngine(use_smart_db=True)
        self.lookback_hours = lookback_hours
        self.symbol_ref = SymbolReferenceEngine()
        self.finbert = FinBERTEngine(use_smart_db=False)  # For per-symbol analysis
        
        logger.info(f"Symbol reference loaded: {len(self.symbol_ref.get_all_symbols())} valid symbols")
    
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Load news, sentiment, and market data"""
        logger.info("Loading data from database...")
        
        # Load news
        news = self.smart_db.query_news_data()
        logger.info(f"  Loaded {len(news):,} news articles")
        
        # Load sentiment
        sentiment = self.smart_db.query_analysis_data(analysis_type='sentiment')
        logger.info(f"  Loaded {len(sentiment):,} sentiment analyses")
        
        # Load market data
        market = self.smart_db.query_market_data()
        logger.info(f"  Loaded {len(market):,} market records")
        
        return news, sentiment, market
    
    def merge_news_sentiment(self, news: pd.DataFrame, sentiment: pd.DataFrame) -> pd.DataFrame:
        """Merge news with sentiment analysis"""
        logger.info("Merging news with sentiment...")
        
        # Merge on link
        merged = news.merge(
            sentiment[['link', 'sentiment', 'confidence', 'positive_score', 
                      'negative_score', 'neutral_score', 'analyzed_at']],
            on='link',
            how='left'
        )
        
        logger.info(f"  Merged: {len(merged):,} records ({len(merged[merged['sentiment'].notna()]):,} with sentiment)")
        
        return merged
    
    def extract_symbols_from_news(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """Extract mentioned symbols from news using validated symbol reference"""
        logger.info("Extracting symbols from news using official symbol reference...")
        
        # Process in chunks with progress
        chunk_size = 1000
        all_symbols = []
        
        for i in range(0, len(news_df), chunk_size):
            chunk = news_df.iloc[i:i+chunk_size]
            
            for _, row in chunk.iterrows():
                text = f"{row.get('title', '')} {row.get('description', '')} {row.get('content', '')}"
                symbols = self.symbol_ref.match_text_to_symbols(text)
                all_symbols.append(symbols)
            
            if (i + chunk_size) % 5000 == 0:
                logger.info(f"  Processed {i+chunk_size:,}/{len(news_df):,} articles...")
        
        news_df['mentioned_symbols'] = all_symbols
        
        # Count mentions
        total_with_symbols = (news_df['mentioned_symbols'].str.len() > 0).sum()
        total_symbols = news_df['mentioned_symbols'].apply(len).sum()
        
        logger.info(f"  Found symbols in {total_with_symbols:,} articles ({total_symbols:,} total mentions)")
        
        return news_df
    
    def ensure_market_data(self, symbols: List[str], start_date: datetime, 
                          end_date: datetime) -> Dict[str, pd.DataFrame]:
        """Ensure we have market data for symbols in date range"""
        logger.info(f"Ensuring market data for {len(symbols)} symbols from {start_date.date()} to {end_date.date()}...")

        market_data: Dict[str, pd.DataFrame] = {}
        missing_symbols = []
        unique_symbols = sorted({s.upper() for s in symbols if s})

        for symbol in unique_symbols:
            # Try loading from DB first
            data = self._load_market_data(symbol, start_date, end_date)

            if data.empty:
                logger.info(f"  No cached data for {symbol}. Fetching via SmartDB connectors...")
                fetched = self._fetch_market_data(symbol, start_date, end_date)
                if not fetched.empty:
                    data = self._load_market_data(symbol, start_date, end_date)

            if data.empty:
                missing_symbols.append(symbol)
                continue

            market_data[symbol] = data

        if missing_symbols:
            logger.warning(
                "  Still missing market data for %d symbols (e.g., %s). Check connector credentials or symbol mapping.",
                len(missing_symbols),
                ", ".join(missing_symbols[:5])
            )
        else:
            logger.info("  Market data ready for all requested symbols")

        return market_data

    def _load_market_data(self, symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Helper to read market data for one symbol from SmartDB."""
        try:
            return self.smart_db.query_market_data(
                symbol=symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
        except Exception as exc:
            logger.warning(f"  Failed to read market data for {symbol}: {exc}")
            return pd.DataFrame()

    def _fetch_market_data(self, symbol: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch missing data via connector and store through SmartDB."""
        asset_class = self._infer_asset_class(symbol)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')

        try:
            if asset_class == 'crypto':
                df = self.connector.get_binance_klines(
                    symbol=symbol,
                    interval='1d',
                    start_str=start_str,
                    end_str=end_str,
                    save_to_db=True
                )
            else:
                df = self.connector.get_yahoo_data(
                    symbol=symbol,
                    start=start_str,
                    end=end_str,
                    interval='1d',
                    save_to_db=True
                )

            if df is None or df.empty:
                logger.warning(f"  Connector returned empty data for {symbol}")
                return pd.DataFrame()

            logger.info(
                "  Stored %d new rows for %s (%s)",
                len(df),
                symbol,
                'binance' if asset_class == 'crypto' else 'yahoo_finance'
            )
            return df

        except Exception as exc:
            logger.error(f"  Failed to fetch data for {symbol}: {exc}")
            return pd.DataFrame()

    def _infer_asset_class(self, symbol: str) -> str:
        """Rudimentary asset-class detection to pick the right connector."""
        symbol = symbol.upper()
        crypto_suffixes = ('USDT', 'USD', 'BTC', 'ETH')
        if any(symbol.endswith(sfx) for sfx in crypto_suffixes):
            return 'crypto'
        return 'stock'
    
    def calculate_price_changes(self, market_data: Dict[str, pd.DataFrame], 
                                news_time: datetime, symbol: str) -> Dict[str, float]:
        """Calculate price changes after news within reasonable time window"""
        if symbol not in market_data:
            return {}
        
        data = market_data[symbol].copy()
        
        # Normalize all timestamps to remove timezone for comparison
        data['timestamp'] = pd.to_datetime(data['timestamp']).dt.tz_localize(None)
        news_time = pd.to_datetime(news_time).tz_localize(None) if hasattr(pd.to_datetime(news_time), 'tz_localize') else pd.to_datetime(news_time)
        
        # Filter data to reasonable window around news time (7 days window)
        window_start = news_time - pd.Timedelta(days=1)
        window_end = news_time + pd.Timedelta(days=7)
        
        data = data[(data['timestamp'] >= window_start) & (data['timestamp'] <= window_end)]
        
        if data.empty:
            return {}
        
        # Get price at news time (or closest after)
        base_price_data = data[data['timestamp'] >= news_time].head(1)
        if base_price_data.empty:
            return {}
        
        base_price = base_price_data['close'].iloc[0]
        changes = {}
        
        # Calculate changes for each lookback period
        for hours in self.lookback_hours:
            target_time = news_time + pd.Timedelta(hours=hours)
            
            # Only calculate if target time is within our data window
            if target_time > window_end:
                continue
            
            target_data = data[data['timestamp'] >= target_time].head(1)
            
            if not target_data.empty:
                target_price = target_data['close'].iloc[0]
                change_pct = ((target_price - base_price) / base_price) * 100
                changes[f'change_{hours}h'] = change_pct
        
        return changes
    
    def analyze_news_impact(self, news_df: pd.DataFrame, 
                           market_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Analyze impact of each news on mentioned symbols with per-symbol sentiment"""
        logger.info("Analyzing news impact on markets with per-symbol sentiment analysis...")
        
        results = []
        
        for idx, row in news_df.iterrows():
            if idx % 100 == 0:
                logger.info(f"  Processed {idx:,}/{len(news_df):,} news articles...")
            
            symbols = row.get('mentioned_symbols', [])
            if not symbols:
                continue
            
            news_time = pd.to_datetime(row['timestamp'])
            
            # Build full text for sentiment analysis
            text = f"{row.get('title', '')} {row.get('description', '')} {row.get('content', '')}"
            
            # Get per-symbol sentiment (highest confidence sentence for each symbol)
            symbol_sentiments = self.finbert.analyze_per_symbol(text, symbols)
            
            for symbol in symbols:
                changes = self.calculate_price_changes(market_data, news_time, symbol)
                
                if changes:
                    # Get symbol-specific sentiment or fall back to article sentiment
                    if symbol in symbol_sentiments:
                        sentiment_data = symbol_sentiments[symbol]
                    else:
                        # Fallback to article-level sentiment
                        sentiment_data = {
                            'sentiment': row.get('sentiment', 'unknown'),
                            'confidence': row.get('confidence', 0),
                            'scores': {
                                'positive': row.get('positive_score', 0),
                                'negative': row.get('negative_score', 0),
                                'neutral': row.get('neutral_score', 0)
                            },
                            'matched_sentence': None
                        }
                    
                    result = {
                        'news_timestamp': news_time,
                        'symbol': symbol,
                        'source': row['source'],
                        'title': row['title'],
                        'link': row['link'],
                        'sentiment': sentiment_data['sentiment'],
                        'confidence': sentiment_data['confidence'],
                        'positive_score': sentiment_data['scores']['positive'],
                        'negative_score': sentiment_data['scores']['negative'],
                        'neutral_score': sentiment_data['scores']['neutral'],
                        'matched_sentence': sentiment_data.get('matched_sentence', None),
                        'is_symbol_specific': symbol in symbol_sentiments
                    }
                    result.update(changes)
                    results.append(result)
        
        logger.info(f"  Generated {len(results):,} news-market correlations")
        
        return pd.DataFrame(results)
    
    def generate_source_accuracy_report(self, impact_df: pd.DataFrame) -> pd.DataFrame:
        """Analyze which news sources have most accurate predictions"""
        logger.info("Analyzing news source accuracy...")
        
        results = []
        
        for source in impact_df['source'].unique():
            source_data = impact_df[impact_df['source'] == source]
            
            for hours in self.lookback_hours:
                col = f'change_{hours}h'
                if col not in source_data.columns:
                    continue
                
                # Filter valid data AND remove extreme movements (outliers)
                valid_data = source_data[source_data[col].notna()].copy()
                
                # QUALITY FILTER: Remove extreme movements (>1000% likely data errors)
                extreme_mask = valid_data[col].abs() > 1000
                if extreme_mask.any():
                    logger.warning(f"  Filtering {extreme_mask.sum()} extreme movements (>1000%) from {source}")
                    valid_data = valid_data[~extreme_mask]
                
                # QUALITY FILTER: Remove top 1% outliers for robust statistics
                if len(valid_data) > 20:
                    percentile_99 = valid_data[col].abs().quantile(0.99)
                    outlier_mask = valid_data[col].abs() > percentile_99
                    if outlier_mask.any():
                        logger.warning(f"  Filtering {outlier_mask.sum()} outliers (>99th percentile) from {source}")
                        valid_data = valid_data[~outlier_mask]
                
                if len(valid_data) < 5:
                    continue
                
                # Predict direction based on sentiment
                valid_data['predicted_direction'] = valid_data['sentiment'].map({
                    'positive': 1,
                    'negative': -1,
                    'neutral': 0
                })
                
                # Actual direction
                valid_data['actual_direction'] = np.sign(valid_data[col])
                
                # Calculate accuracy
                correct_predictions = (
                    valid_data['predicted_direction'] * valid_data['actual_direction'] > 0
                ).sum()
                
                accuracy = (correct_predictions / len(valid_data)) * 100
                
                # Average magnitude of moves (now without outliers)
                avg_move = valid_data[col].abs().mean()
                
                # Confidence correlation
                conf_corr = valid_data['confidence'].corr(valid_data[col].abs())
                
                results.append({
                    'source': source,
                    'timeframe': f'{hours}h',
                    'sample_size': len(valid_data),
                    'accuracy': accuracy,
                    'avg_move': avg_move,
                    'confidence_correlation': conf_corr,
                    'avg_confidence': valid_data['confidence'].mean()
                })
        
        return pd.DataFrame(results)
    
    def generate_symbol_sensitivity_report(self, impact_df: pd.DataFrame) -> pd.DataFrame:
        """Analyze which symbols are most affected by news"""
        logger.info("Analyzing symbol sensitivity to news...")
        
        results = []
        
        for symbol in impact_df['symbol'].unique():
            symbol_data = impact_df[impact_df['symbol'] == symbol]
            
            for hours in self.lookback_hours:
                col = f'change_{hours}h'
                if col not in symbol_data.columns:
                    continue
                
                valid_data = symbol_data[symbol_data[col].notna()].copy()
                
                # QUALITY FILTER: Remove extreme movements and outliers
                extreme_mask = valid_data[col].abs() > 1000
                if extreme_mask.any():
                    logger.warning(f"  Filtering {extreme_mask.sum()} extreme movements from {symbol}")
                    valid_data = valid_data[~extreme_mask]
                
                if len(valid_data) > 20:
                    percentile_99 = valid_data[col].abs().quantile(0.99)
                    outlier_mask = valid_data[col].abs() > percentile_99
                    if outlier_mask.any():
                        logger.warning(f"  Filtering {outlier_mask.sum()} outliers from {symbol}")
                        valid_data = valid_data[~outlier_mask]
                
                if len(valid_data) < 5:
                    continue
                
                # Calculate volatility (now without outliers)
                volatility = valid_data[col].std()
                avg_move = valid_data[col].abs().mean()
                max_move = valid_data[col].abs().max()
                
                # Sentiment correlation
                pos_moves = valid_data[valid_data['sentiment'] == 'positive'][col].mean()
                neg_moves = valid_data[valid_data['sentiment'] == 'negative'][col].mean()
                
                # Count news mentions
                news_count = len(valid_data)
                
                results.append({
                    'symbol': symbol,
                    'timeframe': f'{hours}h',
                    'news_mentions': news_count,
                    'volatility': volatility,
                    'avg_move': avg_move,
                    'max_move': max_move,
                    'positive_avg_move': pos_moves,
                    'negative_avg_move': neg_moves,
                    'sentiment_impact': pos_moves - neg_moves
                })
        
        return pd.DataFrame(results)
    
    def generate_sentiment_effectiveness_report(self, impact_df: pd.DataFrame) -> pd.DataFrame:
        """Analyze overall sentiment prediction effectiveness"""
        logger.info("Analyzing sentiment prediction effectiveness...")
        
        results = []
        
        for hours in self.lookback_hours:
            col = f'change_{hours}h'
            if col not in impact_df.columns:
                continue
            
            valid_data = impact_df[impact_df[col].notna()].copy()
            if len(valid_data) < 10:
                continue
            
            # Overall accuracy
            valid_data['predicted_direction'] = valid_data['sentiment'].map({
                'positive': 1, 'negative': -1, 'neutral': 0
            })
            valid_data['actual_direction'] = np.sign(valid_data[col])
            
            correct = (valid_data['predicted_direction'] * valid_data['actual_direction'] > 0).sum()
            accuracy = (correct / len(valid_data)) * 100
            
            # By sentiment type
            for sentiment in ['positive', 'negative', 'neutral']:
                sent_data = valid_data[valid_data['sentiment'] == sentiment]
                if len(sent_data) < 5:
                    continue
                
                sent_correct = (sent_data['predicted_direction'] * sent_data['actual_direction'] > 0).sum()
                sent_accuracy = (sent_correct / len(sent_data)) * 100
                avg_move = sent_data[col].mean()
                
                results.append({
                    'timeframe': f'{hours}h',
                    'sentiment': sentiment,
                    'sample_size': len(sent_data),
                    'accuracy': sent_accuracy,
                    'avg_price_change': avg_move,
                    'avg_confidence': sent_data['confidence'].mean()
                })
        
        return pd.DataFrame(results)
    
    def save_report(self, report_data: Dict, filename: str = 'news_market_impact_report.json'):
        """Save comprehensive report"""
        report_path = Path(filename)
        
        # Convert DataFrames to dict
        serializable_data = {}
        for key, value in report_data.items():
            if isinstance(value, pd.DataFrame):
                serializable_data[key] = value.to_dict('records')
            else:
                serializable_data[key]= value
        
        with open(report_path, 'w') as f:
            json.dump(serializable_data, f, indent=2, default=str)
        
        logger.info(f"Report saved to {report_path}")
        
        return report_path
    
    def generate_markdown_report(self, report_data: Dict, 
                                 filename: str = 'NEWS_MARKET_IMPACT_REPORT.md'):
        """Generate human-readable markdown report"""
        logger.info("Generating markdown report...")
        
        lines = []
        lines.append("# 📊 News-Market Impact Analysis Report")
        lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("\n---\n")
        
        # Executive Summary
        lines.append("## 📈 Executive Summary\n")
        summary = report_data.get('summary', {})
        lines.append(f"- **Total News Analyzed:** {summary.get('total_news', 0):,}")
        lines.append(f"- **News with Symbols:** {summary.get('news_with_symbols', 0):,}")
        lines.append(f"- **Unique Symbols:** {summary.get('unique_symbols', 0)}")
        lines.append(f"- **News-Market Correlations:** {summary.get('correlations', 0):,}")
        lines.append(f"- **Date Range:** {summary.get('date_range', 'N/A')}")
        lines.append("\n---\n")
        
        # Top Sources by Accuracy
        lines.append("## 🎯 Most Accurate News Sources\n")
        lines.append("Sources with highest prediction accuracy (24h timeframe):\n")
        
        source_acc = pd.DataFrame(report_data.get('source_accuracy', []))
        if not source_acc.empty:
            top_24h = source_acc[source_acc['timeframe'] == '24h'].nlargest(10, 'accuracy')
            lines.append("| Rank | Source | Accuracy | Sample Size | Avg Move | Avg Confidence |")
            lines.append("|------|--------|----------|-------------|----------|----------------|")
            for idx, row in top_24h.iterrows():
                lines.append(f"| {idx+1} | {row['source']} | {row['accuracy']:.1f}% | "
                           f"{row['sample_size']} | {row['avg_move']:.2f}% | "
                           f"{row['avg_confidence']:.1f}% |")
        
        lines.append("\n---\n")
        
        # Most News-Sensitive Symbols
        lines.append("## 📉 Most News-Sensitive Symbols\n")
        lines.append("Symbols with highest volatility after news:\n")
        
        symbol_sens = pd.DataFrame(report_data.get('symbol_sensitivity', []))
        if not symbol_sens.empty:
            top_volatile = symbol_sens[symbol_sens['timeframe'] == '24h'].nlargest(10, 'volatility')
            lines.append("| Rank | Symbol | Volatility | Avg Move | Max Move | News Count |")
            lines.append("|------|--------|------------|----------|----------|------------|")
            for idx, row in top_volatile.iterrows():
                lines.append(f"| {idx+1} | {row['symbol']} | {row['volatility']:.2f}% | "
                           f"{row['avg_move']:.2f}% | {row['max_move']:.2f}% | "
                           f"{row['news_mentions']} |")
        
        lines.append("\n---\n")
        
        # Sentiment Effectiveness
        lines.append("## 🎭 Sentiment Prediction Effectiveness\n")
        
        sent_eff = pd.DataFrame(report_data.get('sentiment_effectiveness', []))
        if not sent_eff.empty:
            for timeframe in ['1h', '4h', '24h', '48h', '168h']:
                tf_data = sent_eff[sent_eff['timeframe'] == timeframe]
                if not tf_data.empty:
                    lines.append(f"\n### {timeframe} Timeframe\n")
                    lines.append("| Sentiment | Accuracy | Sample Size | Avg Price Change |")
                    lines.append("|-----------|----------|-------------|------------------|")
                    for _, row in tf_data.iterrows():
                        lines.append(f"| {row['sentiment'].title()} | {row['accuracy']:.1f}% | "
                                   f"{row['sample_size']} | {row['avg_price_change']:.2f}% |")
        
        lines.append("\n---\n")
        
        # Key Insights
        lines.append("## 💡 Key Insights\n")
        insights = report_data.get('insights', [])
        for insight in insights:
            lines.append(f"- {insight}")
        
        lines.append("\n---\n")
        lines.append("\n*Report generated by WawaBackTrader News-Market Impact Analyzer*\n")
        
        # Save markdown
        report_path = Path(filename)
        with open(report_path, 'w') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Markdown report saved to {report_path}")
        return report_path
    
    def run_analysis(self) -> Dict:
        """Run complete analysis"""
        logger.info("="*70)
        logger.info(" NEWS-MARKET IMPACT ANALYSIS")
        logger.info("="*70)
        
        # Load data
        news, sentiment, market = self.load_data()
        
        # Merge news with sentiment
        news_df = self.merge_news_sentiment(news, sentiment)
        
        # Extract symbols
        news_df = self.extract_symbols_from_news(news_df)
        
        # Filter news with symbols
        news_with_symbols = news_df[news_df['mentioned_symbols'].str.len() > 0].copy()
        
        if news_with_symbols.empty:
            logger.warning("No news with valid symbols found!")
            return {}
        
        logger.info(f"Analyzing {len(news_with_symbols):,} news articles with symbols")
        
        # Get unique symbols from news
        all_symbols = set()
        for symbols in news_with_symbols['mentioned_symbols']:
            all_symbols.update(symbols)
        
        all_symbols = list(all_symbols)
        logger.info(f"Found {len(all_symbols)} unique symbols in news")
        
        # Load market data for all symbols once
        logger.info("Loading market data for all symbols...")
        market_data_by_symbol = {}
        
        for symbol in all_symbols:
            symbol_data = market[market['symbol'] == symbol]
            if not symbol_data.empty:
                market_data_by_symbol[symbol] = symbol_data
        
        logger.info(f"Loaded market data for {len(market_data_by_symbol)} symbols")
        
        # Analyze impact
        impact_df = self.analyze_news_impact(news_with_symbols, market_data_by_symbol)
        
        if impact_df.empty:
            logger.warning("No correlations found!")
            return {}
        
        # Generate reports
        source_accuracy = self.generate_source_accuracy_report(impact_df)
        symbol_sensitivity = self.generate_symbol_sensitivity_report(impact_df)
        sentiment_effectiveness = self.generate_sentiment_effectiveness_report(impact_df)
        
        # Generate insights
        insights = self._generate_insights(source_accuracy, symbol_sensitivity, 
                                          sentiment_effectiveness, impact_df)
        
        # Compile report
        date_range = (news_with_symbols['timestamp'].min(), news_with_symbols['timestamp'].max())
        
        report_data = {
            'summary': {
                'total_news': len(news_df),
                'news_with_symbols': len(news_with_symbols),
                'unique_symbols': len(all_symbols),
                'correlations': len(impact_df),
                'date_range': f"{date_range[0]} to {date_range[1]}",
                'generated_at': datetime.now().isoformat()
            },
            'source_accuracy': source_accuracy,
            'symbol_sensitivity': symbol_sensitivity,
            'sentiment_effectiveness': sentiment_effectiveness,
            'impact_data': impact_df,
            'insights': insights
        }
        
        # Save reports
        json_path = self.save_report(report_data)
        md_path = self.generate_markdown_report(report_data)
        
        logger.info("="*70)
        logger.info(" ANALYSIS COMPLETE")
        logger.info("="*70)
        logger.info(f"JSON Report: {json_path}")
        logger.info(f"Markdown Report: {md_path}")
        
        return report_data
    
    def _generate_insights(self, source_acc: pd.DataFrame, symbol_sens: pd.DataFrame,
                          sent_eff: pd.DataFrame, impact_df: pd.DataFrame) -> List[str]:
        """Generate key insights from analysis"""
        insights = []
        
        # Best source
        if not source_acc.empty:
            best_source = source_acc.nlargest(1, 'accuracy').iloc[0]
            insights.append(
                f"**Most Accurate Source:** {best_source['source']} with "
                f"{best_source['accuracy']:.1f}% accuracy over {best_source['sample_size']} predictions"
            )
        
        # Most volatile symbol
        if not symbol_sens.empty:
            most_volatile = symbol_sens.nlargest(1, 'volatility').iloc[0]
            insights.append(
                f"**Most News-Sensitive Symbol:** {most_volatile['symbol']} with "
                f"{most_volatile['volatility']:.2f}% average volatility after news"
            )
        
        # Best sentiment accuracy
        if not sent_eff.empty:
            best_sentiment = sent_eff.nlargest(1, 'accuracy').iloc[0]
            insights.append(
                f"**Most Predictive Sentiment:** {best_sentiment['sentiment'].title()} sentiment "
                f"has {best_sentiment['accuracy']:.1f}% accuracy in {best_sentiment['timeframe']}"
            )
        
        # Overall correlation
        if not impact_df.empty:
            for hours in [1, 24, 168]:
                col = f'change_{hours}h'
                if col in impact_df.columns:
                    valid = impact_df[impact_df[col].notna()]
                    if len(valid) > 0:
                        avg_move = valid[col].abs().mean()
                        insights.append(
                            f"**Average Price Move ({hours}h):** {avg_move:.2f}% after news announcement"
                        )
                        break
        
        return insights


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='News-Market Impact Analysis')
    parser.add_argument('--lookback', type=int, nargs='+', 
                       default=[1, 4, 24, 48, 168],
                       help='Lookback periods in hours (default: 1 4 24 48 168)')
    
    args = parser.parse_args()
    
    try:
        analyzer = NewsMarketAnalyzer(lookback_hours=args.lookback)
        report = analyzer.run_analysis()
        
        print("\n" + "="*70)
        print(" Analysis complete! Check the generated reports:")
        print("  - news_market_impact_report.json")
        print("  - NEWS_MARKET_IMPACT_REPORT.md")
        print("="*70)
        
    except KeyboardInterrupt:
        logger.warning("\nAnalysis interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
