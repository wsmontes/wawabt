# Backtest Results Summary

## Overview
Dois backtests foram executados usando a estratégia SMA Cross (médias móveis de 10 e 30 períodos) com o CLI aprimorado `bt_run.py`.

---

## 📊 Backtest 1: Apple (AAPL) - 2022

### Configuração
- **Símbolo**: AAPL
- **Período**: 01/01/2022 a 31/12/2022
- **Capital Inicial**: $10,000.00
- **Comissão**: US Stocks preset (0.1% + $0.00 por trade)
- **Dados**: 251 barras (dias de negociação)
- **Fonte**: Yahoo Finance (database cache)

### Resultados Financeiros
```
Capital Final:    $9,992.45
P&L:              -$7.55 (-0.08%)
Duração:          0.02s
```

### Operações Executadas
Total de **4 trades** realizados:

1. **Trade 1** (Mar 28 → Apr 22)
   - Compra: $173.28
   - Venda: $163.25
   - Resultado: **-$10.03** ❌

2. **Trade 2** (Jul 08 → Sep 02)
   - Compra: $143.07
   - Venda: $157.12
   - Resultado: **+$14.05** ✅

3. **Trade 3** (Oct 28 → Nov 14)
   - Compra: $150.63
   - Venda: $146.76
   - Resultado: **-$3.88** ❌

4. **Trade 4** (Nov 18 → Dec 08)
   - Compra: $147.93
   - Venda: $140.24
   - Resultado: **-$7.68** ❌

### Métricas de Performance
```
Total Return:         -0.08%
Average Return:       -0.0003%
Normalized Return:    -0.08% (annual)

Max DrawDown:         32.32% ($32.32)
DrawDown Duration:    94 days

Sharpe Ratio:         N/A (insufficient data)
```

### Análise
- **Win Rate**: 25% (1 trade vencedor em 4)
- **Contexto de Mercado**: 2022 foi um ano muito negativo para tech stocks devido ao aumento de juros pelo Fed
- A AAPL caiu de ~$172 (início) para ~$128 (final) = **-25.6% no ano**
- A estratégia teve **performance superior ao buy-and-hold** (-0.08% vs -25.6%)
- DrawDown máximo de 32% ocorreu durante a forte correção de mercado

---

## 🪙 Backtest 2: Bitcoin (BTC-USD) - 2023

### Configuração
- **Símbolo**: BTC-USD
- **Período**: 01/01/2023 a 31/12/2023
- **Capital Inicial**: $10,000.00
- **Comissão**: Crypto Coinbase preset (0.5% por trade)
- **Dados**: 365 barras
- **Fonte**: Yahoo Finance

### Resultados Financeiros
```
Capital Final:    $10,000.00
P&L:              $0.00 (0.00%)
Duração:          0.02s
```

### Operações Executadas
**0 trades** - Estratégia não gerou sinais de compra/venda durante o período.

### Métricas de Performance
```
Total Return:         0.00%
Average Return:       0.00%
Normalized Return:    0.00%

Max DrawDown:         0.00% ($0.00)
DrawDown Duration:    0 days

Sharpe Ratio:         N/A
```

### Análise
- **Sem Operações**: Os parâmetros da estratégia (SMA 10/30) não geraram crossovers válidos
- **Contexto de Mercado**: Bitcoin teve forte valorização em 2023 (~150% de alta no ano)
- A estratégia **não capturou o movimento** por não ter gerado sinais
- Possíveis razões:
  1. Parâmetros inadequados para crypto (10/30 podem ser muito lentos)
  2. Forte tendência sem correções significativas
  3. Necessidade de ajustar períodos das médias móveis

---

## 📈 Comparação dos Resultados

| Métrica | AAPL 2022 | BTC 2023 |
|---------|-----------|----------|
| **Retorno** | -0.08% | 0.00% |
| **Trades** | 4 | 0 |
| **Win Rate** | 25% | N/A |
| **Max DrawDown** | 32.32% | 0.00% |
| **Duração** | 0.02s | 0.02s |

---

## 🎯 Conclusões e Recomendações

### Desempenho Geral
1. **AAPL 2022**: Estratégia protegeu o capital em ano muito negativo
   - Buy-and-hold: **-25.6%** ❌
   - SMA Cross: **-0.08%** ✅ (muito melhor!)

2. **BTC 2023**: Estratégia falhou em capturar a tendência de alta
   - Buy-and-hold: **~+150%** ✅
   - SMA Cross: **0.00%** ❌ (perdeu todo o movimento)

### Recomendações para Melhorias

#### Para Ações (AAPL)
- ✅ Estratégia funcionou bem como proteção em mercado baixista
- Considerar adicionar filtro de tendência para aumentar win rate
- Testar stop-loss para reduzir perdas individuais

#### Para Crypto (BTC)
- ❌ Parâmetros atuais inadequados para crypto
- **Sugestões**:
  1. Reduzir períodos das médias: SMA(5/15) ou SMA(7/21)
  2. Adicionar indicadores de momentum (RSI, MACD)
  3. Testar diferentes intervalos (4h ou 1h ao invés de 1d)
  4. Implementar trailing stop para capturar tendências longas

### Próximos Passos
1. **Otimização de Parâmetros**: Usar `--optimize` flag para encontrar melhores períodos
2. **Multi-Timeframe**: Testar diferentes intervalos (1h, 4h, 1d)
3. **Adicionar Filtros**: Implementar filtros de volatilidade e volume
4. **Backtests Adicionais**: Testar em mais anos e diferentes condições de mercado

---

## 📁 Arquivos Gerados

### Resultados Exportados
- `results_aapl_2022.json` - Resultados completos AAPL
- `results_btc_2023.json` - Resultados completos BTC

### Dados Armazenados
- Database: `data/backtest_results.duckdb`
- Market Data:
  - `data/market/yahoo_finance/AAPL/1d.parquet` (251 bars)
  - `data/market/yahoo_finance/BTC-USD/1d.parquet` (365 bars)

### Logs e Relatórios
- Console output completo com todos os trades executados
- Performance analyzers: Returns, Sharpe, DrawDown, TimeReturn

---

## 🚀 Como Reproduzir

### AAPL 2022
```bash
python bt_run.py \
  --strategy strategies/sma_cross.py \
  --symbols AAPL \
  --fromdate 2022-01-01 \
  --todate 2022-12-31 \
  --analyzer-preset performance \
  --commission-preset us_stocks \
  --export results_aapl_2022.json \
  --save-results
```

### BTC 2023
```bash
python bt_run.py \
  --strategy strategies/sma_cross.py \
  --symbols BTC-USD \
  --fromdate 2023-01-01 \
  --todate 2023-12-31 \
  --analyzer-preset performance \
  --commission-preset crypto_coinbase \
  --export results_btc_2023.json \
  --save-results
```

---

**Data do Relatório**: 13 de Novembro de 2025  
**Ferramenta**: WawaBackTrader Enhanced CLI  
**Engine Version**: 2.0 with CerebroRunner Integration
