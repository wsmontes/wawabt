# WawaBackTrader - Copilot Instructions

**WawaBackTrader** é uma versão aprimorada do [backtrader](https://www.backtrader.com/) com gerenciamento inteligente de dados financeiros, suportando múltiplas fontes de dados e integração com banco de dados DuckDB/Parquet.

### Propósito Principal
- Framework de backtesting para estratégias de trading
- Gerenciamento automático de dados de mercado (OHLCV)
- Coleta e armazenamento de notícias RSS
- Arquitetura "database-first" com auto-fetch e auto-save

## Arquitetura e Padrões

### Hierarquia de Diretórios
```
backtrader/          # Framework core (indicators, strategies, brokers)
engines/             # Engines de dados (connector, database, rss, smart_db)
strategies/          # Estratégias de trading customizadas
config/              # Arquivos de configuração JSON
data/                # Dados armazenados (market, news, metrics, logs)
docs/                # Documentação técnica
```

### Padrões de Código
1. **Separation of Concerns**: Cada engine tem responsabilidade específica
2. **Database-First**: Sempre verificar database antes de fazer fetch externo
3. **Auto-Save**: Dados fetched são automaticamente salvos em Parquet
4. **Intelligent Partitioning**: Dados particionados por symbol/date/interval
5. **Deduplication**: Constraints únicos para evitar duplicação

### Nomenclatura
- **Engines**: Classes terminam com `Engine` (ex: `ConnectorEngine`, `RSSEngine`)
- **Strategies**: Herdam de `bt.Strategy`, arquivo em `strategies/`
- **Configs**: Arquivos JSON em `config/` (ex: `connector.json`, `rss_sources.json`)
- **Data Feeds**: Usar `AutoFetchData` ou `create_data_feed()` para feeds automáticos

## Engines Principais

### 1. **ConnectorEngine** (`engines/connector.py`)
- Conecta com fontes externas: Yahoo Finance, Binance, CCXT, Alpaca, Quandl

### 2. **SmartDatabaseManager** (`engines/smart_db.py`)
- Gerencia DuckDB + Parquet para armazenamento eficiente

### 3. **RSSEngine** (`engines/rss.py`)
- Coleta notícias de feeds RSS (Bloomberg, Reuters, Yahoo, CNBC, CoinDesk)

### 4. **DatabaseEngine** (`engines/database.py`)
- Interface legacy para SQLite (manter compatibilidade)

### 5. **AutoFetchData** (`engines/bt_data.py`)
- Feed de dados do backtrader com auto-fetch

## Convenções de Uso

### Ao criar strategies:
```python
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (('period', 20),)  # Parâmetros configuráveis
    
    def __init__(self):
        self.sma = bt.indicators.SMA(self.data.close, period=self.params.period)
    
    def next(self):
        if self.data.close[0] > self.sma[0]:
            self.buy()
```

### Ao usar engines:
```python
from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager

# Database-first approach
connector = ConnectorEngine(use_smart_db=True)
df = connector.get_yahoo_data('AAPL', period='1mo', interval='1d')
# Dados salvos automaticamente em: data/market/yahoo_finance/AAPL/1d.parquet
```

### Ao executar backtests:
```bash
# Formato: python bt_run.py --strategy <file> --symbols <symbols> [options]
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL GOOGL --cash 100000 --plot
```

## Prioridades de Desenvolvimento

1. **Sempre verificar database primeiro** antes de fetch externo
2. **Usar SmartDatabaseManager** para novos recursos (não DatabaseEngine legacy)
3. **Manter deduplicação** em todas as operações de save
4. **Particionar dados** por symbol/interval quando apropriado
5. **Documentar** em `docs/` apenas funcionalidades novas. Preferir atualizar documentos existentes.
6. **Testar** em `tests/`, preferir atualizar testes existentes.
7. **Use VENV** e não esqueça de ativar o ambiente virtual antes de rodar qualquer programa.
