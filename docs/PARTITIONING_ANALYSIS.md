# Análise de Particionamento de Dados - WawaBackTrader

**Data:** 14 de Novembro de 2025  
**Autor:** Sistema de Análise

## 🎯 Problema Identificado

Durante a validação do sistema RSS, foi identificada uma **incoerência no particionamento de news data**:

### Situação Atual
- **Path do arquivo:** `data/news/{source}/{YEAR}/{MONTH}.parquet`
- **Critério de particionamento:** Data **ATUAL** (quando o fetch é executado)
- **Problema:** Dados com timestamps de períodos anteriores são salvos no arquivo do mês atual

### Exemplo Real
```
Arquivo: data/news/Yahoo Finance/2025/11.parquet
├─ Organização: 2025/11 (novembro de 2025)
├─ Contém: 46 registros
├─ Range de datas: 2025-09-04 até 2025-11-12
└─ Problema: 1 registro de SETEMBRO está no arquivo de NOVEMBRO
```

## 📊 Análise de Impacto

### ✅ Impactos BAIXOS:
1. **Query Performance:** Queries funcionam normalmente, DuckDB lê os parquets corretamente
2. **Deduplicação:** Sistema de deduplicação funciona (não há duplicatas)
3. **Data Integrity:** Dados não são corrompidos ou perdidos
4. **Funcionalidade:** Sistema RSS salva e recupera dados corretamente

### ⚠️ Impactos MÉDIOS:
1. **Organização Semântica:** Incoerência entre nome do arquivo e conteúdo
2. **Queries por Período:** Para buscar dados de setembro, precisa ler arquivo de novembro
3. **Data Retention:** Políticas de retenção por período podem não funcionar adequadamente
4. **Manutenção:** Confusão ao investigar dados ou fazer limpezas manuais

### ❌ Impactos ALTOS:
- **Nenhum** - O sistema continua funcional

## 🏗️ Estrutura de Dados Atual

### Market Data (✅ Correto)
```
data/market/{source}/{symbol}/{interval}.parquet
```
- **Não usa data no path** → Correto!
- Motivo: Market data pode ter fetch histórico de qualquer período
- Um único arquivo por symbol/interval contém todo histórico

### News Data (⚠️ Inconsistente)
```
data/news/{source}/{year}/{month}.parquet
```
- **Usa data ATUAL** → Inconsistente
- Problema: RSS feeds retornam dados de vários períodos
- Dados antigos misturados com dados novos no mesmo arquivo

## 💡 Soluções Propostas

### Opção 1: Particionar por Período dos DADOS ⭐ RECOMENDADA
**Implementação:** Usar timestamp dos dados para determinar o path

```python
# Atual (data de escrita)
file_path = f"data/news/{source}/{datetime.now().year}/{datetime.now().month}.parquet"

# Proposto (data dos dados)
for year, month in data.groupby(['timestamp.year', 'timestamp.month']):
    file_path = f"data/news/{source}/{year}/{month}.parquet"
```

**Vantagens:**
- ✅ Dados sempre no local semanticamente correto
- ✅ Melhor performance de queries por período
- ✅ Facilita políticas de retenção de dados
- ✅ Alinhado com a semântica esperada

**Desvantagens:**
- ⚠️ Pode criar múltiplos arquivos pequenos se houver fetch histórico
- ⚠️ Dados novos de períodos antigos vão para arquivos antigos

### Opção 2: Particionar Apenas por FONTE
**Implementação:** Um único arquivo por fonte

```python
file_path = f"data/news/{source}/all_data.parquet"
```

**Vantagens:**
- ✅ Simplicidade extrema
- ✅ Fácil de gerenciar
- ✅ Sem preocupação com datas

**Desvantagens:**
- ❌ Arquivos podem crescer indefinidamente
- ❌ Queries por período menos eficientes
- ❌ Dificulta retenção e limpeza de dados antigos

### Opção 3: Status Quo (Não Fazer Nada)
**Implementação:** Manter estrutura atual

**Vantagens:**
- ✅ Não requer mudanças
- ✅ Sistema funciona adequadamente

**Desvantagens:**
- ❌ Incoerência semântica permanece
- ❌ Possível confusão em análises futuras

## 🎯 Recomendação Final

### Para RSS/News Data: **Opção 1** 
Implementar particionamento baseado no timestamp dos dados

**Razão:**
- News/RSS tem natureza temporal forte
- Queries comuns: "notícias de outubro", "últimos 7 dias"
- Facilita manutenção e políticas de retenção
- Alinha expectativa com realidade

### Para Market Data: **Manter Atual** ✅
Sem data no path, apenas source/symbol/interval

**Razão:**
- Market data pode ter fetch histórico de qualquer período
- Um único arquivo contém todo histórico de um símbolo
- Estrutura atual é adequada para o caso de uso

## 🔧 Implementação

Foi criado o arquivo `smart_news_partitioner.py` que implementa:

1. **SmartNewsPartitioner**: Classe que particiona por período dos dados
2. **Reorganização automática**: Script para reorganizar dados existentes
3. **Dry Run mode**: Testa mudanças antes de aplicar

### Como Usar:

```bash
# Testar sem fazer mudanças
python smart_news_partitioner.py

# Aplicar reorganização (responder 'y' quando perguntado)
python smart_news_partitioner.py
```

### Integração com SmartDatabaseManager

Para aplicar a solução, o método `store_news_data` em `smart_db.py` deve ser modificado para:

```python
def store_news_data(self, df: pd.DataFrame, source: str):
    # Particionar por ano/mês dos DADOS
    for (year, month), group_df in df.groupby([df['timestamp'].dt.year, df['timestamp'].dt.month]):
        file_path = self._get_file_path('news_data', source=source, year=year, month=month)
        # ... salvar cada grupo no arquivo correto
```

## 📋 Checklist de Implementação

- [x] Análise do problema
- [x] Identificação de impactos
- [x] Proposta de soluções
- [x] Criação de script de reorganização
- [ ] Modificar `SmartDatabaseManager.store_news_data()`
- [ ] Testar com dados existentes
- [ ] Reorganizar dados históricos
- [ ] Atualizar documentação
- [ ] Validar queries após reorganização

## 🚦 Status Atual

**DECISÃO PENDENTE:** Aguardando confirmação para implementar Opção 1

**Sistema Funcional:** ✅ Sim, sistema continua operacional
**Urgência:** 🟡 Média (não bloqueia operação, mas melhora organização)
**Esforço:** 🟢 Baixo (script já pronto, requer teste e validação)

## 📚 Arquivos Relacionados

- `analyze_partitioning.py` - Análise completa do problema
- `smart_news_partitioner.py` - Implementação da solução
- `engines/smart_db.py` - Código atual do particionamento
- `config/database.json` - Configuração de estrutura de dados