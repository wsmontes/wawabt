#!/usr/bin/env python3
"""
Sentiment Champion Strategy Builder
Análise completa de correlação sentimento-preço usando dados ESPECÍFICOS por símbolo
Cria features e estratégia campeã baseada em 474 eventos de notícias com impacto medido
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import json
import logging
from typing import Dict, List
import duckdb

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('SentimentChampion')


class SentimentChampionAnalyzer:
    """
    Análise de sentimento para criação de estratégia campeã
    Usa dados reais de impacto de notícias em símbolos específicos
    """
    
    def __init__(self, impact_file: str = 'data/analysis/news_impact_by_symbol.parquet'):
        """Inicializa com arquivo de impacto de notícias"""
        self.impact_file = impact_file
        self.conn = duckdb.connect('data/market_data.duckdb')
        logger.info(f"Carregando dados de: {impact_file}")
        
    def load_impact_data(self) -> pd.DataFrame:
        """Carrega dados de impacto de notícias por símbolo"""
        df = pd.read_parquet(self.impact_file)
        df['news_timestamp'] = pd.to_datetime(df['news_timestamp'])
        
        logger.info(f"Carregados {len(df)} eventos de notícias")
        logger.info(f"Símbolos: {df['symbol'].nunique()} únicos")
        logger.info(f"Período: {df['news_timestamp'].min()} a {df['news_timestamp'].max()}")
        
        return df
    
    def create_sentiment_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria score de sentimento composto (-1 a +1)
        """
        logger.info("Criando sentiment scores...")
        
        df = df.copy()
        
        # Score baseado em positive - negative, ponderado por confidence
        df['sentiment_score'] = (df['positive_score'] - df['negative_score']) * df['confidence']
        
        # Normalizar entre -1 e 1
        df['sentiment_score'] = df['sentiment_score'].clip(-1, 1)
        
        # Sentiment categórico como número
        sentiment_map = {'positive': 1, 'neutral': 0, 'negative': -1}
        df['sentiment_numeric'] = df['sentiment'].map(sentiment_map)
        
        # Strength do sentimento (absoluto)
        df['sentiment_strength'] = df['sentiment_score'].abs()
        
        # Flags binários
        df['is_positive'] = (df['sentiment'] == 'positive').astype(int)
        df['is_negative'] = (df['sentiment'] == 'negative').astype(int)
        df['is_neutral'] = (df['sentiment'] == 'neutral').astype(int)
        
        return df
    
    def calculate_correlations(self, df: pd.DataFrame) -> Dict:
        """
        Calcula correlações entre sentimento e mudanças de preço
        Para cada janela de tempo (1h, 4h, 24h, 48h, 168h)
        """
        logger.info("Calculando correlações sentimento-preço...")
        
        results = {
            'overall': {},
            'by_symbol': {},
            'by_sentiment': {}
        }
        
        # Correlações gerais
        time_windows = ['change_1h', 'change_4h', 'change_24h', 'change_48h', 'change_168h']
        
        for window in time_windows:
            valid_data = df[['sentiment_score', window]].dropna()
            if len(valid_data) > 10:
                corr = valid_data['sentiment_score'].corr(valid_data[window])
                results['overall'][window] = {
                    'correlation': float(corr),
                    'sample_size': len(valid_data)
                }
                logger.info(f"  {window}: corr={corr:.4f} (n={len(valid_data)})")
        
        # Correlações por símbolo
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol]
            if len(symbol_df) < 5:
                continue
            
            symbol_results = {}
            for window in time_windows:
                valid_data = symbol_df[['sentiment_score', window]].dropna()
                if len(valid_data) > 3:
                    corr = valid_data['sentiment_score'].corr(valid_data[window])
                    symbol_results[window] = {
                        'correlation': float(corr),
                        'sample_size': len(valid_data)
                    }
            
            if symbol_results:
                results['by_symbol'][symbol] = symbol_results
        
        # Correlações por tipo de sentimento
        for sentiment in ['positive', 'negative', 'neutral']:
            sent_df = df[df['sentiment'] == sentiment]
            if len(sent_df) < 5:
                continue
            
            sent_results = {}
            for window in time_windows:
                valid_data = sent_df[[window]].dropna()
                if len(valid_data) > 3:
                    sent_results[window] = {
                        'mean_return': float(valid_data[window].mean()),
                        'std_return': float(valid_data[window].std()),
                        'sample_size': len(valid_data)
                    }
            
            if sent_results:
                results['by_sentiment'][sentiment] = sent_results
        
        return results
    
    def calculate_predictive_power(self, df: pd.DataFrame) -> Dict:
        """
        Calcula poder preditivo do sentimento
        Verifica accuracy na previsão de direção (up/down)
        """
        logger.info("Calculando poder preditivo...")
        
        results = {}
        time_windows = ['change_1h', 'change_4h', 'change_24h', 'change_48h', 'change_168h']
        
        for window in time_windows:
            valid_df = df[['sentiment_numeric', 'sentiment_score', window]].dropna()
            
            if len(valid_df) < 10:
                continue
            
            # Accuracy: sentimento prevê direção correta?
            correct_direction = (
                ((valid_df['sentiment_numeric'] > 0) & (valid_df[window] > 0)) |
                ((valid_df['sentiment_numeric'] < 0) & (valid_df[window] < 0)) |
                ((valid_df['sentiment_numeric'] == 0) & (valid_df[window].abs() < 0.5))
            )
            
            accuracy = correct_direction.mean()
            
            # Retornos médios por direção de sentimento
            positive_returns = valid_df[valid_df['sentiment_numeric'] > 0][window].mean()
            negative_returns = valid_df[valid_df['sentiment_numeric'] < 0][window].mean()
            neutral_returns = valid_df[valid_df['sentiment_numeric'] == 0][window].mean()
            
            results[window] = {
                'accuracy': float(accuracy),
                'sample_size': len(valid_df),
                'positive_mean_return': float(positive_returns) if not pd.isna(positive_returns) else 0,
                'negative_mean_return': float(negative_returns) if not pd.isna(negative_returns) else 0,
                'neutral_mean_return': float(neutral_returns) if not pd.isna(neutral_returns) else 0
            }
            
            logger.info(f"  {window}: accuracy={accuracy:.2%} (n={len(valid_df)})")
        
        return results
    
    def generate_trading_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gera sinais de trading baseados em sentimento
        """
        logger.info("Gerando sinais de trading...")
        
        df = df.copy()
        
        # Signal 1: Simple Sentiment Threshold
        df['signal_simple'] = 0
        df.loc[df['sentiment_score'] > 0.3, 'signal_simple'] = 1  # Buy
        df.loc[df['sentiment_score'] < -0.3, 'signal_simple'] = -1  # Sell
        
        # Signal 2: High Confidence Sentiment
        df['signal_high_conf'] = 0
        df.loc[(df['sentiment_score'] > 0.2) & (df['confidence'] > 0.8), 'signal_high_conf'] = 1
        df.loc[(df['sentiment_score'] < -0.2) & (df['confidence'] > 0.8), 'signal_high_conf'] = -1
        
        # Signal 3: Strong Sentiment (only extremes)
        df['signal_strong'] = 0
        df.loc[df['sentiment_score'] > 0.5, 'signal_strong'] = 1
        df.loc[df['sentiment_score'] < -0.5, 'signal_strong'] = -1
        
        # Signal 4: Specific News (is_symbol_specific flag)
        df['signal_specific'] = 0
        df.loc[(df['is_symbol_specific']) & (df['sentiment_score'] > 0.2), 'signal_specific'] = 1
        df.loc[(df['is_symbol_specific']) & (df['sentiment_score'] < -0.2), 'signal_specific'] = -1
        
        logger.info("Sinais gerados: simple, high_conf, strong, specific")
        
        return df
    
    def backtest_signals(self, df: pd.DataFrame) -> Dict:
        """
        Backtest simples dos sinais gerados
        """
        logger.info("Backtesting sinais...")
        
        results = {}
        signal_cols = [c for c in df.columns if c.startswith('signal_')]
        time_windows = ['change_1h', 'change_4h', 'change_24h', 'change_48h', 'change_168h']
        
        for signal_col in signal_cols:
            signal_results = {}
            
            for window in time_windows:
                # Calcular retornos do sinal
                valid_df = df[[signal_col, window]].dropna()
                valid_df = valid_df[valid_df[signal_col] != 0]  # Apenas trades ativos
                
                if len(valid_df) == 0:
                    continue
                
                # Retorno do sinal (multiplicar sinal por retorno)
                signal_returns = valid_df[signal_col] * valid_df[window]
                
                # Métricas
                total_trades = len(valid_df)
                winning_trades = (signal_returns > 0).sum()
                losing_trades = (signal_returns < 0).sum()
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                
                avg_return = signal_returns.mean()
                avg_win = signal_returns[signal_returns > 0].mean() if winning_trades > 0 else 0
                avg_loss = signal_returns[signal_returns < 0].mean() if losing_trades > 0 else 0
                
                # Sharpe ratio
                sharpe = (signal_returns.mean() / signal_returns.std() * np.sqrt(252)) if signal_returns.std() > 0 else 0
                
                # Total return (soma de retornos)
                total_return = signal_returns.sum()
                
                signal_results[window] = {
                    'total_trades': int(total_trades),
                    'winning_trades': int(winning_trades),
                    'losing_trades': int(losing_trades),
                    'win_rate': float(win_rate),
                    'avg_return': float(avg_return),
                    'avg_win': float(avg_win),
                    'avg_loss': float(avg_loss),
                    'sharpe_ratio': float(sharpe),
                    'total_return': float(total_return)
                }
            
            results[signal_col] = signal_results
        
        # Log best performers
        logger.info("\nMelhores sinais:")
        for signal, windows in results.items():
            best_window = max(windows.items(), key=lambda x: x[1]['sharpe_ratio'])
            logger.info(f"  {signal} @ {best_window[0]}: Sharpe={best_window[1]['sharpe_ratio']:.2f}, Win%={best_window[1]['win_rate']:.1%}")
        
        return results
    
    def create_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cria matriz de features para ML
        """
        logger.info("Criando matriz de features para ML...")
        
        features = df.copy()
        
        # Features de sentimento
        sentiment_features = [
            'sentiment_score', 'sentiment_strength', 'sentiment_numeric',
            'positive_score', 'negative_score', 'neutral_score',
            'confidence', 'is_positive', 'is_negative', 'is_neutral',
            'is_symbol_specific'
        ]
        
        # Features de target (mudanças de preço)
        target_features = [
            'change_1h', 'change_4h', 'change_24h', 'change_48h', 'change_168h'
        ]
        
        # Features de contexto
        features['news_timestamp'] = pd.to_datetime(features['news_timestamp'], utc=True)
        features['hour_of_day'] = features['news_timestamp'].dt.hour
        features['day_of_week'] = features['news_timestamp'].dt.dayofweek
        features['is_market_hours'] = ((features['hour_of_day'] >= 9) & (features['hour_of_day'] <= 16)).astype(int)
        
        # Symbol encoding (one-hot para principais símbolos)
        top_symbols = features['symbol'].value_counts().head(10).index
        for symbol in top_symbols:
            features[f'is_{symbol}'] = (features['symbol'] == symbol).astype(int)
        
        all_features = sentiment_features + target_features + ['hour_of_day', 'day_of_week', 'is_market_hours']
        all_features += [f'is_{s}' for s in top_symbols]
        
        feature_matrix = features[all_features + ['symbol', 'news_timestamp']]
        
        logger.info(f"Matriz de features criada: {feature_matrix.shape}")
        logger.info(f"Features: {len(all_features)}")
        
        return feature_matrix
    
    def find_best_strategy(self, backtest_results: Dict) -> Dict:
        """
        Identifica a melhor estratégia baseada em Sharpe Ratio
        """
        logger.info("Identificando melhor estratégia...")
        
        best_strategy = {
            'signal': None,
            'window': None,
            'sharpe': -999,
            'metrics': {}
        }
        
        for signal, windows in backtest_results.items():
            for window, metrics in windows.items():
                if metrics['sharpe_ratio'] > best_strategy['sharpe']:
                    best_strategy['signal'] = signal
                    best_strategy['window'] = window
                    best_strategy['sharpe'] = metrics['sharpe_ratio']
                    best_strategy['metrics'] = metrics
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🏆 MELHOR ESTRATÉGIA: {best_strategy['signal']} @ {best_strategy['window']}")
        logger.info(f"{'='*80}")
        logger.info(f"Sharpe Ratio: {best_strategy['sharpe']:.2f}")
        logger.info(f"Win Rate: {best_strategy['metrics']['win_rate']:.1%}")
        logger.info(f"Total Trades: {best_strategy['metrics']['total_trades']}")
        logger.info(f"Avg Return: {best_strategy['metrics']['avg_return']:.4f}")
        logger.info(f"Total Return: {best_strategy['metrics']['total_return']:.2%}")
        logger.info(f"{'='*80}\n")
        
        return best_strategy
    
    def save_results(self, data: Dict, filename: str):
        """Salva resultados em JSON"""
        output_dir = Path('results/analysis')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"✅ Resultados salvos em: {output_path}")
    
    def run_complete_analysis(self):
        """
        Executa análise completa
        """
        logger.info("="*80)
        logger.info("🚀 SENTIMENT CHAMPION STRATEGY ANALYSIS")
        logger.info("="*80)
        
        # 1. Carregar dados
        df = self.load_impact_data()
        
        # 2. Criar sentiment scores
        df = self.create_sentiment_score(df)
        
        # 3. Correlações
        correlations = self.calculate_correlations(df)
        
        # 4. Poder preditivo
        predictive_power = self.calculate_predictive_power(df)
        
        # 5. Gerar sinais
        df_with_signals = self.generate_trading_signals(df)
        
        # 6. Backtest
        backtest_results = self.backtest_signals(df_with_signals)
        
        # 7. Best strategy
        best_strategy = self.find_best_strategy(backtest_results)
        
        # 8. Feature matrix
        feature_matrix = self.create_feature_matrix(df_with_signals)
        
        # 9. Salvar resultados
        self.save_results({
            'correlations': correlations,
            'predictive_power': predictive_power,
            'backtest_results': backtest_results,
            'best_strategy': best_strategy,
            'summary': {
                'total_events': len(df),
                'symbols': df['symbol'].nunique(),
                'date_range': f"{df['news_timestamp'].min()} to {df['news_timestamp'].max()}",
                'sentiment_distribution': df['sentiment'].value_counts().to_dict(),
                'generated_at': datetime.now().isoformat()
            }
        }, 'sentiment_champion_analysis.json')
        
        # Salvar feature matrix
        feature_matrix.to_parquet('results/analysis/sentiment_champion_features.parquet', index=False)
        logger.info("✅ Feature matrix salva em: results/analysis/sentiment_champion_features.parquet")
        
        # Salvar dataset com sinais
        df_with_signals.to_parquet('results/analysis/sentiment_champion_signals.parquet', index=False)
        logger.info("✅ Dataset com sinais salvo em: results/analysis/sentiment_champion_signals.parquet")
        
        logger.info("="*80)
        logger.info("✅ ANÁLISE COMPLETA FINALIZADA")
        logger.info("="*80)
        logger.info("\n📊 PRÓXIMOS PASSOS:")
        logger.info("1. Revisar results/analysis/sentiment_champion_analysis.json")
        logger.info("2. Usar results/analysis/sentiment_champion_features.parquet para ML")
        logger.info("3. Implementar best_strategy em strategies/")
        logger.info("4. Executar backtest completo com bt_run.py")
        logger.info("="*80)
        
        return {
            'df': df_with_signals,
            'correlations': correlations,
            'predictive_power': predictive_power,
            'backtest_results': backtest_results,
            'best_strategy': best_strategy,
            'feature_matrix': feature_matrix
        }


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sentiment Champion Strategy Analysis')
    parser.add_argument('--impact-file', default='data/analysis/news_impact_by_symbol.parquet',
                       help='Arquivo de impacto de notícias')
    
    args = parser.parse_args()
    
    # Executar análise
    analyzer = SentimentChampionAnalyzer(impact_file=args.impact_file)
    results = analyzer.run_complete_analysis()


if __name__ == '__main__':
    main()
