#!/usr/bin/env python3
"""
Sentiment Analysis Champion Strategy Builder
Cria análise completa de correlação sentimento-preço e features para ML
Gera todos os dados necessários para criar uma estratégia campeã
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('SentimentChampion')


class SentimentAnalysisChampion:
    """
    Análise completa de sentimento para criação de estratégia campeã
    """
    
    def __init__(self, db_path: str = 'data/market_data.duckdb'):
        """Inicializa conexão com banco de dados"""
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        logger.info(f"Conectado ao banco: {db_path}")
        
    def load_sentiment_data(self, symbols: List[str] = None) -> pd.DataFrame:
        """
        Carrega dados de sentimento do banco
        
        Args:
            symbols: Lista de símbolos para filtrar (None = todos)
        """
        logger.info("Carregando dados de sentimento...")
        
        query = """
            SELECT timestamp, source, title, link, sentiment, confidence,
                   positive_score, negative_score, neutral_score,
                   symbol, category, analysis_type
            FROM read_parquet('data/analysis/sentiment/**/*.parquet')
            WHERE symbol IS NOT NULL AND symbol != ''
        """
        
        if symbols:
            symbols_str = "', '".join(symbols)
            query += f" AND symbol IN ('{symbols_str}')"
        
        df = self.conn.execute(query).fetchdf()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        logger.info(f"Carregados {len(df):,} registros de sentimento")
        logger.info(f"Símbolos únicos: {df['symbol'].nunique()}")
        logger.info(f"Período: {df['timestamp'].min()} a {df['timestamp'].max()}")
        
        return df
    
    def load_market_data(self, symbols: List[str] = None, interval: str = '1d') -> pd.DataFrame:
        """
        Carrega dados de mercado do banco
        
        Args:
            symbols: Lista de símbolos para filtrar
            interval: Intervalo de tempo (1d, 1h, etc)
        """
        logger.info(f"Carregando dados de mercado (interval={interval})...")
        
        query = """
            SELECT timestamp, symbol, open, high, low, close, volume, interval
            FROM read_parquet('data/market/**/*.parquet', hive_partitioning=true)
        """
        
        conditions = []
        if symbols:
            symbols_str = "', '".join(symbols)
            conditions.append(f"symbol IN ('{symbols_str}')")
        if interval:
            conditions.append(f"interval = '{interval}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        df = self.conn.execute(query).fetchdf()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculate returns
        df = df.sort_values(['symbol', 'timestamp'])
        df['returns'] = df.groupby('symbol')['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df.groupby('symbol')['close'].shift(1))
        
        logger.info(f"Carregados {len(df):,} registros de mercado")
        logger.info(f"Símbolos únicos: {df['symbol'].nunique()}")
        
        return df
    
    def create_sentiment_score(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria score de sentimento composto
        
        Score vai de -1 (muito negativo) a +1 (muito positivo)
        Considera confidence e scores individuais
        """
        logger.info("Criando sentiment score composto...")
        
        df = sentiment_df.copy()
        
        # Sentiment score base: positive - negative
        df['sentiment_score'] = (df['positive_score'] - df['negative_score']) * df['confidence']
        
        # Normalizar entre -1 e 1
        df['sentiment_score'] = df['sentiment_score'].clip(-1, 1)
        
        # Sentiment categórico como número
        sentiment_map = {'positive': 1, 'neutral': 0, 'negative': -1}
        df['sentiment_numeric'] = df['sentiment'].map(sentiment_map)
        
        return df
    
    def aggregate_sentiment_daily(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """
        Agrega sentimento por símbolo e dia
        """
        logger.info("Agregando sentimento por dia...")
        
        df = sentiment_df.copy()
        df['date'] = df['timestamp'].dt.date
        
        # Agregar por símbolo e data
        agg_df = df.groupby(['symbol', 'date']).agg({
            'sentiment_score': ['mean', 'std', 'min', 'max', 'count'],
            'sentiment_numeric': 'mean',
            'confidence': 'mean',
            'positive_score': 'mean',
            'negative_score': 'mean',
            'neutral_score': 'mean',
            'source': 'nunique'  # Número de fontes diferentes
        }).reset_index()
        
        # Flatten multi-index columns
        agg_df.columns = ['_'.join(col).strip('_') if col[1] else col[0] 
                         for col in agg_df.columns.values]
        
        # Renomear colunas
        agg_df.rename(columns={
            'sentiment_score_mean': 'sentiment_mean',
            'sentiment_score_std': 'sentiment_volatility',
            'sentiment_score_min': 'sentiment_min',
            'sentiment_score_max': 'sentiment_max',
            'sentiment_score_count': 'news_volume',
            'sentiment_numeric_mean': 'sentiment_direction',
            'confidence_mean': 'avg_confidence',
            'source_nunique': 'sources_count'
        }, inplace=True)
        
        # Preencher NaN em volatilidade (dias com apenas 1 notícia)
        agg_df['sentiment_volatility'].fillna(0, inplace=True)
        
        logger.info(f"Agregado para {len(agg_df):,} dias/símbolos")
        
        return agg_df
    
    def create_sentiment_features(self, sentiment_df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria features avançadas de sentimento para ML
        """
        logger.info("Criando features de sentimento...")
        
        df = sentiment_df.sort_values(['symbol', 'date']).copy()
        
        # Features de momentum
        for window in [3, 7, 14, 30]:
            df[f'sentiment_ma_{window}d'] = df.groupby('symbol')['sentiment_mean'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )
            df[f'sentiment_momentum_{window}d'] = df['sentiment_mean'] - df[f'sentiment_ma_{window}d']
        
        # Features de volatilidade
        for window in [7, 14, 30]:
            df[f'sentiment_vol_{window}d'] = df.groupby('symbol')['sentiment_mean'].transform(
                lambda x: x.rolling(window, min_periods=1).std()
            )
        
        # Features de volume de notícias
        for window in [3, 7, 14]:
            df[f'news_volume_ma_{window}d'] = df.groupby('symbol')['news_volume'].transform(
                lambda x: x.rolling(window, min_periods=1).mean()
            )
        
        # Mudança de sentimento (shift)
        df['sentiment_change_1d'] = df.groupby('symbol')['sentiment_mean'].diff()
        df['sentiment_change_3d'] = df.groupby('symbol')['sentiment_mean'].diff(3)
        df['sentiment_change_7d'] = df.groupby('symbol')['sentiment_mean'].diff(7)
        
        # Sentiment extremes (flags)
        df['is_very_positive'] = (df['sentiment_mean'] > 0.5).astype(int)
        df['is_very_negative'] = (df['sentiment_mean'] < -0.5).astype(int)
        df['is_high_volume'] = (df['news_volume'] > df['news_volume'].quantile(0.75)).astype(int)
        
        # Sentiment strength (absoluto)
        df['sentiment_strength'] = df['sentiment_mean'].abs()
        
        logger.info(f"Criadas {len([c for c in df.columns if 'sentiment' in c or 'news' in c])} features")
        
        return df
    
    def merge_sentiment_with_market(self, sentiment_df: pd.DataFrame, 
                                    market_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge sentimento com dados de mercado
        """
        logger.info("Merging sentimento com dados de mercado...")
        
        # Converter timestamp para date em market_df
        market_df['date'] = market_df['timestamp'].dt.date
        
        # Merge
        merged = pd.merge(
            market_df,
            sentiment_df,
            on=['symbol', 'date'],
            how='left'
        )
        
        # Preencher NaN (dias sem notícias) com 0
        sentiment_cols = [c for c in sentiment_df.columns if c not in ['symbol', 'date']]
        merged[sentiment_cols] = merged[sentiment_cols].fillna(0)
        
        logger.info(f"Merged dataset: {len(merged):,} registros")
        
        return merged
    
    def calculate_correlation_analysis(self, merged_df: pd.DataFrame) -> Dict:
        """
        Calcula correlações entre sentimento e retornos
        Testa diferentes lags e leads
        """
        logger.info("Calculando análise de correlação...")
        
        results = {}
        
        # Correlações por símbolo
        symbols = merged_df['symbol'].unique()
        
        for symbol in symbols:
            df_symbol = merged_df[merged_df['symbol'] == symbol].copy()
            df_symbol = df_symbol.sort_values('timestamp')
            
            if len(df_symbol) < 30:  # Mínimo de dados
                continue
            
            symbol_results = {}
            
            # Correlação contemporânea
            corr_contemp = df_symbol[['sentiment_mean', 'returns']].corr().iloc[0, 1]
            symbol_results['correlation_contemporaneous'] = corr_contemp
            
            # Correlações com lags (sentimento -> retorno futuro)
            for lag in [1, 2, 3, 5, 7, 14, 30]:
                future_returns = df_symbol['returns'].shift(-lag)
                corr = df_symbol['sentiment_mean'].corr(future_returns)
                symbol_results[f'correlation_lead_{lag}d'] = corr
            
            # Correlações com leads (retorno passado -> sentimento)
            for lead in [1, 2, 3, 5, 7]:
                past_returns = df_symbol['returns'].shift(lead)
                corr = df_symbol['sentiment_mean'].corr(past_returns)
                symbol_results[f'correlation_lag_{lead}d'] = corr
            
            # Adicionar info básica
            symbol_results['total_observations'] = len(df_symbol)
            symbol_results['avg_sentiment'] = df_symbol['sentiment_mean'].mean()
            symbol_results['avg_return'] = df_symbol['returns'].mean()
            symbol_results['volatility'] = df_symbol['returns'].std()
            
            results[symbol] = symbol_results
        
        logger.info(f"Análise de correlação completa para {len(results)} símbolos")
        
        return results
    
    def calculate_predictive_power(self, merged_df: pd.DataFrame, 
                                   prediction_window: int = 5) -> pd.DataFrame:
        """
        Calcula poder preditivo do sentimento
        Verifica se sentimento positivo/negativo prediz retornos futuros
        """
        logger.info(f"Calculando poder preditivo (window={prediction_window}d)...")
        
        df = merged_df.copy()
        df = df.sort_values(['symbol', 'timestamp'])
        
        # Criar target: retorno futuro
        df['future_return'] = df.groupby('symbol')['returns'].shift(-prediction_window)
        
        # Criar bins de sentimento
        df['sentiment_bin'] = pd.cut(df['sentiment_mean'], 
                                     bins=[-np.inf, -0.3, -0.1, 0.1, 0.3, np.inf],
                                     labels=['very_negative', 'negative', 'neutral', 
                                            'positive', 'very_positive'])
        
        # Agrupar por bin de sentimento
        predictive_power = df.groupby('sentiment_bin').agg({
            'future_return': ['mean', 'std', 'count'],
            'returns': ['mean', 'std']
        }).reset_index()
        
        predictive_power.columns = ['_'.join(col).strip('_') if col[1] else col[0] 
                                   for col in predictive_power.columns.values]
        
        # Calcular accuracy: % de vezes que sentimento previu direção correta
        df['prediction_correct'] = (
            ((df['sentiment_mean'] > 0) & (df['future_return'] > 0)) |
            ((df['sentiment_mean'] < 0) & (df['future_return'] < 0))
        )
        
        accuracy = df.groupby('sentiment_bin')['prediction_correct'].agg(['mean', 'count'])
        
        logger.info(f"\nPoder Preditivo ({prediction_window}d forward):")
        logger.info(f"\n{predictive_power}")
        logger.info(f"\nAccuracy por Sentimento:")
        logger.info(f"\n{accuracy}")
        
        return predictive_power
    
    def generate_trading_signals(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de trading baseados em sentimento
        """
        logger.info("Gerando sinais de trading...")
        
        df = merged_df.copy()
        
        # Signal 1: Sentiment Threshold
        df['signal_sentiment_threshold'] = 0
        df.loc[df['sentiment_mean'] > 0.3, 'signal_sentiment_threshold'] = 1  # Buy
        df.loc[df['sentiment_mean'] < -0.3, 'signal_sentiment_threshold'] = -1  # Sell
        
        # Signal 2: Sentiment Momentum
        df['signal_sentiment_momentum'] = 0
        df.loc[(df['sentiment_momentum_7d'] > 0.1) & 
               (df['sentiment_mean'] > 0), 'signal_sentiment_momentum'] = 1
        df.loc[(df['sentiment_momentum_7d'] < -0.1) & 
               (df['sentiment_mean'] < 0), 'signal_sentiment_momentum'] = -1
        
        # Signal 3: Combined (Sentiment + Volume)
        df['signal_combined'] = 0
        df.loc[(df['sentiment_mean'] > 0.2) & 
               (df['is_high_volume'] == 1), 'signal_combined'] = 1
        df.loc[(df['sentiment_mean'] < -0.2) & 
               (df['is_high_volume'] == 1), 'signal_combined'] = -1
        
        # Signal 4: Sentiment Reversal
        df['signal_reversal'] = 0
        df.loc[(df['sentiment_mean'] < -0.5) & 
               (df['sentiment_change_3d'] > 0.2), 'signal_reversal'] = 1  # Bounce
        df.loc[(df['sentiment_mean'] > 0.5) & 
               (df['sentiment_change_3d'] < -0.2), 'signal_reversal'] = -1  # Correction
        
        logger.info("Sinais gerados: threshold, momentum, combined, reversal")
        
        return df
    
    def backtest_signals(self, df_with_signals: pd.DataFrame) -> Dict:
        """
        Backtest simples dos sinais gerados
        """
        logger.info("Backtesting sinais...")
        
        results = {}
        signal_cols = [c for c in df_with_signals.columns if c.startswith('signal_')]
        
        for signal_col in signal_cols:
            df = df_with_signals.copy()
            
            # Calcular retornos do sinal (próximo período)
            df['signal_return'] = df.groupby('symbol')['returns'].shift(-1) * df[signal_col]
            
            # Métricas
            total_trades = (df[signal_col] != 0).sum()
            winning_trades = (df['signal_return'] > 0).sum()
            losing_trades = (df['signal_return'] < 0).sum()
            
            if total_trades > 0:
                win_rate = winning_trades / total_trades
                avg_return = df[df[signal_col] != 0]['signal_return'].mean()
                avg_win = df[df['signal_return'] > 0]['signal_return'].mean()
                avg_loss = df[df['signal_return'] < 0]['signal_return'].mean()
                sharpe = df['signal_return'].mean() / df['signal_return'].std() if df['signal_return'].std() > 0 else 0
                
                results[signal_col] = {
                    'total_trades': int(total_trades),
                    'winning_trades': int(winning_trades),
                    'losing_trades': int(losing_trades),
                    'win_rate': float(win_rate),
                    'avg_return': float(avg_return),
                    'avg_win': float(avg_win) if not pd.isna(avg_win) else 0,
                    'avg_loss': float(avg_loss) if not pd.isna(avg_loss) else 0,
                    'sharpe_ratio': float(sharpe)
                }
        
        logger.info(f"\nBacktest Results:")
        for signal, metrics in results.items():
            logger.info(f"\n{signal}:")
            logger.info(f"  Total trades: {metrics['total_trades']}")
            logger.info(f"  Win rate: {metrics['win_rate']:.2%}")
            logger.info(f"  Avg return: {metrics['avg_return']:.4f}")
            logger.info(f"  Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        
        return results
    
    def save_results(self, data: Dict, filename: str):
        """Salva resultados em JSON"""
        output_dir = Path('data/analysis')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Resultados salvos em: {output_path}")
    
    def save_dataset(self, df: pd.DataFrame, filename: str):
        """Salva dataset em Parquet"""
        output_dir = Path('data/analysis')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        df.to_parquet(output_path, index=False)
        
        logger.info(f"Dataset salvo em: {output_path}")
    
    def run_complete_analysis(self, symbols: List[str] = None, top_n: int = 20):
        """
        Executa análise completa
        
        Args:
            symbols: Lista de símbolos (None = usa top símbolos por volume)
            top_n: Se symbols=None, usa top N símbolos
        """
        logger.info("="*80)
        logger.info("INICIANDO ANÁLISE COMPLETA DE SENTIMENTO")
        logger.info("="*80)
        
        # 1. Carregar dados
        sentiment_df = self.load_sentiment_data(symbols)
        
        if symbols is None:
            # Usar top símbolos por volume de análises
            top_symbols = sentiment_df['symbol'].value_counts().head(top_n).index.tolist()
            # Filtrar Cointelegraph que são tags, não símbolos
            top_symbols = [s for s in top_symbols if s not in ['Cointelegraph', 'Cointelegraph_Content']][:top_n]
            logger.info(f"Usando top {len(top_symbols)} símbolos: {top_symbols}")
            sentiment_df = sentiment_df[sentiment_df['symbol'].isin(top_symbols)]
        
        # 2. Criar sentiment scores
        sentiment_df = self.create_sentiment_score(sentiment_df)
        
        # 3. Agregar por dia
        daily_sentiment = self.aggregate_sentiment_daily(sentiment_df)
        
        # 4. Criar features
        sentiment_features = self.create_sentiment_features(daily_sentiment)
        
        # 5. Carregar dados de mercado
        symbols_list = sentiment_features['symbol'].unique().tolist()
        market_df = self.load_market_data(symbols_list, interval='1d')
        
        # 6. Merge
        merged_df = self.merge_sentiment_with_market(sentiment_features, market_df)
        
        # 7. Análise de correlação
        correlation_results = self.calculate_correlation_analysis(merged_df)
        
        # 8. Poder preditivo
        predictive_power = self.calculate_predictive_power(merged_df, prediction_window=5)
        
        # 9. Gerar sinais
        df_with_signals = self.generate_trading_signals(merged_df)
        
        # 10. Backtest
        backtest_results = self.backtest_signals(df_with_signals)
        
        # 11. Salvar resultados
        self.save_results(correlation_results, 'sentiment_correlation_analysis.json')
        self.save_results(backtest_results, 'sentiment_backtest_results.json')
        self.save_dataset(df_with_signals, 'sentiment_features_complete.parquet')
        
        logger.info("="*80)
        logger.info("ANÁLISE COMPLETA FINALIZADA")
        logger.info("="*80)
        
        return {
            'merged_df': merged_df,
            'df_with_signals': df_with_signals,
            'correlation_results': correlation_results,
            'backtest_results': backtest_results
        }


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sentiment Analysis Champion')
    parser.add_argument('--symbols', nargs='+', help='Símbolos para analisar')
    parser.add_argument('--top-n', type=int, default=20, help='Top N símbolos se --symbols não fornecido')
    parser.add_argument('--db-path', default='data/market_data.duckdb', help='Caminho do banco de dados')
    
    args = parser.parse_args()
    
    # Executar análise
    analyzer = SentimentAnalysisChampion(db_path=args.db_path)
    results = analyzer.run_complete_analysis(symbols=args.symbols, top_n=args.top_n)
    
    logger.info("\n" + "="*80)
    logger.info("PRÓXIMOS PASSOS:")
    logger.info("="*80)
    logger.info("1. Revisar data/analysis/sentiment_correlation_analysis.json")
    logger.info("2. Analisar data/analysis/sentiment_backtest_results.json")
    logger.info("3. Usar data/analysis/sentiment_features_complete.parquet para ML")
    logger.info("4. Criar estratégia em strategies/ baseada nos melhores sinais")
    logger.info("="*80)


if __name__ == '__main__':
    main()
