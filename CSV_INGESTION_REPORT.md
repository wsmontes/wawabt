# Relatório de Ingestão de Arquivos CSV

**Data:** 14 de Novembro de 2025  
**Executado por:** CSV News Ingestor

---

## 📁 Arquivos Analisados

### 1. `cointelegraph_news_head.csv`
- **Tamanho:** 44 MB
- **Total de linhas:** 25,719
- **Status:** ✅ **INGERIDO COM SUCESSO**

#### Dados do Arquivo
- **Período:** 2020 (April 2020 visível)
- **Fonte:** Cointelegraph - Metadados de notícias crypto
- **Campos principais:**
  - `title` - Título da notícia
  - `lead`/`leadfull` - Descrição/resumo
  - `url` - Link completo
  - `publishedW3` - Timestamp ISO 8601
  - `category_title` - Categoria (Latest News, Market Analysis, Opinion, etc.)
  - `author_title` - Nome do autor
  - `author_img` - Imagem do autor
  - Múltiplos campos de imagens (retina, thumb, amp_thumb)

#### Resultado da Ingestão
- **Registros carregados:** 25,471
- **Registros válidos:** 22,769 (após filtro de datas)
- **Registros salvos no DB:** 22,763 (após deduplicação)
- **Arquivos Parquet gerados:** 64 (particionados por ano/mês)
- **Taxa de sucesso:** 89.4%

#### Particionamento
```
data/news/Cointelegraph/
├── 2020/
│   ├── 01.parquet
│   ├── 02.parquet
│   ├── 03.parquet
│   ├── 04.parquet
│   └── ... (até 12.parquet)
```

---

### 2. `cointelegraph_news_content.csv`
- **Tamanho:** 83 MB
- **Total de linhas:** 25,471
- **Status:** ✅ **INGERIDO COM SUCESSO** (com tratamento de encoding)

#### Dados do Arquivo
- **Período:** 2020 (similar ao head.csv)
- **Fonte:** Cointelegraph Content - Conteúdo completo dos artigos
- **Campos principais:**
  - `id` - ID único do artigo
  - `header` - Título (equivalente a title)
  - `date` - Data de publicação
  - `total_views` - Visualizações totais
  - `total_shares` - Compartilhamentos
  - `content` - **Conteúdo completo do artigo (texto longo)**

#### Resultado da Ingestão
- **Registros carregados:** 25,469 (com `on_bad_lines='skip'` por vírgulas no conteúdo)
- **Registros válidos:** 22,636 (após filtro de datas)
- **Registros salvos no DB:** 44,594 total no DB após ingestão
- **Arquivos Parquet gerados:** 64 (particionados por ano/mês)
- **Taxa de sucesso:** 88.9%
- **Source name:** `Cointelegraph_Content` (diferenciado do head)

#### Observações Técnicas
- Arquivo requereu tratamento especial de CSV devido a vírgulas no campo `content`
- Usado `quotechar='"'` e `escapechar='\\'` para parsing correto
- URLs reconstruídas como: `https://cointelegraph.com/news/{id}`

---

### 3. `QuandlData.csv`
- **Tamanho:** 605 KB
- **Total de linhas:** 4,110
- **Status:** ⚠️ **NÃO INGERIDO** (não é notícia)

#### Dados do Arquivo
- **Período:** 2019-2020 (March-April 2020 visível)
- **Tipo:** Métricas de Bitcoin (Market Data)
- **Campos principais:**
  - `CostPerTransaction` - Custo por transação
  - `Difficulty` - Dificuldade de mineração
  - `HashRate` - Taxa de hash da rede
  - `MarketCapitalization` - Capitalização de mercado
  - `MinerRevenue` - Receita dos mineradores
  - `TransactionsPerDay` - Transações por dia
  - `UniqueAddress` - Endereços únicos
  - `NumberOfTransactions` - Número de transações
  - `ExchangeTradeVolume` - Volume de trade

#### Decisão
❌ **Arquivo NÃO deve ser ingerido na tabela de notícias**
- Dados são **métricas quantitativas**, não artigos de notícias
- Adequado para uma tabela separada de **market_data** ou **bitcoin_metrics**
- Pode ser usado para análise de correlação com notícias

#### Recomendação
Se desejado, criar uma nova tabela específica:
```python
# Proposta de estrutura
smart_db.store_bitcoin_metrics(
    df=quandl_df,
    source='Quandl',
    asset='BTC'
)
```

---

## 📊 Resumo da Ingestão

### Estatísticas Finais do Banco de Dados

```
Total de registros no DB: 46,196
Fontes únicas: 76
```

#### Breakdown por Fonte
| Fonte | Registros |
|-------|-----------|
| Cointelegraph (head) | 22,763 |
| Cointelegraph_Content | ~21,831 (calculado) |
| Outras fontes RSS | 1,602 |

### Arquivos Processados
- ✅ **2 arquivos ingeridos** com sucesso
- ⚠️ **1 arquivo ignorado** (não é notícia)
- 📁 **128 arquivos Parquet** gerados (64 por cada fonte Cointelegraph)

### Período Coberto
- **2020:** Cobertura completa de notícias crypto do Cointelegraph
- **2025:** Notícias RSS coletadas (September-November)

---

## 🎯 Validação de Qualidade

### ✅ Pontos Fortes
1. **Deduplicação funcionando:** Sistema detectou e evitou duplicatas por `link + timestamp`
2. **Particionamento correto:** Dados organizados por timestamp da notícia (não da escrita)
3. **Filtro de qualidade:** Removeu ~10% de registros com timestamps inválidos ou fora do range
4. **Encoding tratado:** CSV com conteúdo complexo processado corretamente

### ⚠️ Pontos de Atenção
1. **URLs no content.csv:** Foram reconstruídas como `cointelegraph.com/news/{id}` - verificar se estão corretas
2. **Linhas malformadas:** 2 linhas puladas no content.csv por problemas de parsing
3. **Diferença de registros:** head (22,763) vs content (21,831) - investigar gap de ~932 registros

### 🔍 Sugestões de Melhoria
1. **Cruzamento de dados:** Fazer join entre head e content por ID para enriquecer registros
2. **Bitcoin metrics:** Criar engine separado para market data do Quandl
3. **Validação de URLs:** Script para testar se URLs reconstruídas estão funcionais
4. **Gap analysis:** Identificar quais IDs estão no head mas não no content

---

## 🚀 Próximos Passos

### Imediatos
- [x] Ingestão de cointelegraph_news_head.csv
- [x] Ingestão de cointelegraph_news_content.csv
- [x] Validação de QuandlData.csv

### Sugeridos
- [ ] Criar `store_bitcoin_metrics()` para dados do Quandl
- [ ] Script de análise de gap entre head e content
- [ ] Validação de URLs reconstruídas
- [ ] Query de exemplo para acessar dados completos (head + content)

---

## 📝 Comandos Executados

```bash
# Ingestão do arquivo head
python ingest_csv_news.py sources/cointelegraph_news_head.csv --auto-detect

# Ingestão do arquivo content (após fix de encoding)
python ingest_csv_news.py sources/cointelegraph_news_content.csv --auto-detect

# Análise dos arquivos
wc -l sources/*.csv
ls -lh sources/*.csv
```

---

## 💾 Estado do Banco de Dados

### DuckDB Views Criadas
```sql
-- View unificada de todos os períodos
CREATE VIEW IF NOT EXISTS Cointelegraph_all AS 
SELECT * FROM read_parquet('data/news/Cointelegraph/*/*.parquet');

CREATE VIEW IF NOT EXISTS Cointelegraph_Content_all AS 
SELECT * FROM read_parquet('data/news/Cointelegraph_Content/*/*.parquet');
```

### Exemplo de Query
```python
from engines.smart_db import SmartDatabaseManager

smart_db = SmartDatabaseManager()

# Buscar todas as notícias Cointelegraph
ct_news = smart_db.query_news_data(source='Cointelegraph')

# Buscar por período específico
april_2020 = smart_db.query_news_data(
    source='Cointelegraph',
    start_date='2020-04-01',
    end_date='2020-04-30'
)

# Buscar conteúdo completo
full_content = smart_db.query_news_data(source='Cointelegraph_Content')
```

---

**Status Final:** ✅ Ingestão concluída com sucesso!
