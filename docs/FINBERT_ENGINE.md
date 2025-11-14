# FinBERT Sentiment Analysis Engine

## Visão Geral

O **FinBERTEngine** é uma engine de análise de sentimento especializada em textos financeiros, usando o modelo [FinBERT](https://huggingface.co/ProsusAI/finbert) da ProsusAI. 

FinBERT é um modelo BERT pré-treinado especificamente para análise de sentimento em comunicações financeiras (notícias, relatórios, tweets, etc.).

## Características

- ✅ **Análise de Sentimento Financeiro**: Especializado em linguagem financeira
- ✅ **3 Classes**: positive, negative, neutral
- ✅ **Scores de Confiança**: Para cada classe (0-1)
- ✅ **Batch Processing**: Análise eficiente de múltiplos textos
- ✅ **Integração com Database**: Salva resultados via `SmartDatabaseManager`
- ✅ **CPU e GPU**: Suporte para aceleração GPU (opcional)

## Instalação

### Opção 1: Script Automático
```bash
bash install_finbert.sh
```

### Opção 2: Manual
```bash
# CPU only (mais leve)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers sentencepiece protobuf

# Com GPU (requer CUDA)
pip install torch torchvision torchaudio
pip install transformers sentencepiece protobuf
```

## Uso Básico

### 1. Análise de Texto Único

```python
from engines.finbert import FinBERTEngine

engine = FinBERTEngine()

result = engine.analyze_sentiment("Apple stock soars to record high")

print(result)
# {
#     'sentiment': 'positive',
#     'confidence': 0.98,
#     'scores': {
#         'positive': 0.98,
#         'negative': 0.01,
#         'neutral': 0.01
#     }
# }
```

### 2. Análise de DataFrame

```python
import pandas as pd
from engines.finbert import FinBERTEngine

engine = FinBERTEngine()

# DataFrame com notícias
news_df = pd.DataFrame({
    'title': ['Stock prices surge', 'Market crash fears'],
    'description': ['...', '...']
})

# Analisa e adiciona colunas de sentiment
result_df = engine.analyze_news_df(news_df)

print(result_df[['title', 'sentiment', 'sentiment_confidence']])
```

### 3. Análise e Salvamento no Database

```python
from engines.finbert import FinBERTEngine

engine = FinBERTEngine(use_smart_db=True)

# Analisa notícias do CoinDesk e salva no database
result_df = engine.analyze_and_save(
    source='CoinDesk',
    start_date='2025-11-01',
    end_date='2025-11-14',
    limit=100
)

print(f"Analisados: {len(result_df)} artigos")
```

### 4. Resumo de Sentimento

```python
from engines.finbert import FinBERTEngine

engine = FinBERTEngine(use_smart_db=True)

summary = engine.get_sentiment_summary(
    source='CoinDesk',
    start_date='2025-11-01',
    end_date='2025-11-14'
)

print(summary)
# {
#     'total': 100,
#     'positive': 45,
#     'negative': 20,
#     'neutral': 35,
#     'positive_pct': 45.0,
#     'negative_pct': 20.0,
#     'neutral_pct': 35.0,
#     'avg_confidence': 0.87
# }
```

## CLI - Linha de Comando

### Análise de Texto
```bash
python engines/finbert.py --text "Bitcoin surges past $100k milestone"
```

### Análise de Notícias do Database
```bash
# Analisa e salva
python engines/finbert.py --source CoinDesk --limit 100

# Com filtro de data
python engines/finbert.py --source "Yahoo Finance" \
    --start-date 2025-11-01 \
    --end-date 2025-11-14

# Resumo de sentimento
python engines/finbert.py --summary --source CoinDesk
```

### GPU Acceleration
```bash
# Usa GPU se disponível
python engines/finbert.py --text "..." --device cuda
```

## Exemplos

Execute exemplos prontos:

```bash
# Todos os exemplos
python examples/finbert_examples.py

# Exemplo específico
python examples/finbert_examples.py --example 1  # Texto único
python examples/finbert_examples.py --example 2  # Análise de news
python examples/finbert_examples.py --example 3  # Salvar no DB
python examples/finbert_examples.py --example 4  # Resumo
```

## Estrutura de Dados Salvos

Os resultados são salvos via `SmartDatabaseManager.store_analysis_data()`:

```
data/analysis/sentiment/
├── CoinDesk/
│   └── sentiment_analysis.parquet
├── Yahoo_Finance/
│   └── sentiment_analysis.parquet
└── all_news/
    └── sentiment_analysis.parquet
```

### Schema dos Dados

```python
{
    'timestamp': datetime,           # Data da notícia
    'source': str,                   # Fonte da notícia
    'title': str,                    # Título
    'link': str,                     # URL
    'sentiment': str,                # 'positive', 'negative', 'neutral'
    'confidence': float,             # Confiança (0-1)
    'positive_score': float,         # Score positivo (0-1)
    'negative_score': float,         # Score negativo (0-1)
    'neutral_score': float,          # Score neutro (0-1)
    'analyzed_at': datetime,         # Timestamp da análise
    'category': str                  # Categoria (se disponível)
}
```

## Integração com Backtesting

### Usar Sentimento em Estratégias

```python
import backtrader as bt
from engines.finbert import FinBERTEngine
from engines.smart_db import SmartDatabaseManager

class SentimentStrategy(bt.Strategy):
    def __init__(self):
        self.finbert = FinBERTEngine()
        self.smart_db = SmartDatabaseManager()
    
    def next(self):
        # Pega data atual do backtest
        current_date = self.data.datetime.date(0)
        
        # Busca sentimento do dia
        news = self.smart_db.query_news_data(
            source='CoinDesk',
            start_date=str(current_date),
            end_date=str(current_date)
        )
        
        if not news.empty:
            # Analisa sentimento
            sentiment_df = self.finbert.analyze_news_df(news)
            
            # Score médio do dia
            avg_positive = sentiment_df['sentiment_positive'].mean()
            
            # Trading logic baseado em sentimento
            if avg_positive > 0.7 and not self.position:
                self.buy()
            elif avg_positive < 0.3 and self.position:
                self.sell()
```

## Performance

### Velocidade
- **CPU**: ~10-20 texts/segundo
- **GPU**: ~100-200 texts/segundo
- **Batch processing**: Aumenta eficiência

### Memória
- **Modelo**: ~400 MB
- **Por análise**: ~10 KB

### Recomendações
- Use `batch_size=16` para equilíbrio entre velocidade e memória
- Para grandes volumes (>10k), use GPU se disponível
- Cache resultados no database para evitar reprocessamento

## Classes de Sentimento

### Positive (Bullish)
Indica otimismo, crescimento, notícias favoráveis:
- "Stock prices surge on strong earnings"
- "Bitcoin reaches new all-time high"
- "Company reports record profits"

### Negative (Bearish)
Indica pessimismo, queda, notícias desfavoráveis:
- "Market crash fears escalate"
- "Stock plummets on earnings miss"
- "Recession concerns mount"

### Neutral
Indica fatos objetivos, sem clara direção:
- "Federal Reserve announces rate decision"
- "Company releases quarterly report"
- "Trading volume remains stable"

## Troubleshooting

### Erro: "transformers not found"
```bash
pip install transformers torch
```

### Erro: "CUDA out of memory"
```python
# Use CPU
engine = FinBERTEngine(device='cpu')

# Ou reduza batch_size
results = engine.analyze_batch(texts, batch_size=8)
```

### Modelo demora muito para carregar
**Normal!** Primeiro download (~400MB) demora. Depois é cacheado localmente em `~/.cache/huggingface/`

### Resultados parecem incorretos
- FinBERT é especializado em **linguagem financeira**
- Para textos genéricos, pode não funcionar bem
- Confidence score baixo (<0.5) indica incerteza

## Referências

- **FinBERT Paper**: [FinBERT: A Pre-trained Financial Language Model](https://arxiv.org/abs/2006.08097)
- **HuggingFace Model**: [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert)
- **BERT Original**: [Devlin et al., 2018](https://arxiv.org/abs/1810.04805)

## TODO / Melhorias Futuras

- [ ] Suporte para análise multilíngue
- [ ] Cache de resultados para acelerar reprocessamento
- [ ] Agregação de sentimento por símbolo/asset
- [ ] Dashboard web para visualização
- [ ] Fine-tuning para crypto news específico
- [ ] Integração com alertas em tempo real
