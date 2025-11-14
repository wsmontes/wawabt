#!/usr/bin/env python3
"""
Análise detalhada da coerência de particionamento de dados
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
from collections import defaultdict

sys.path.insert(0, os.path.abspath('.'))

def analyze_news_partitioning():
    """Analisa o particionamento de news data"""
    print("=== ANÁLISE DE PARTICIONAMENTO - NEWS DATA ===\n")
    
    news_dir = Path('data/news')
    if not news_dir.exists():
        print("❌ Diretório data/news não existe")
        return
    
    issues = []
    total_files = 0
    total_records = 0
    
    for parquet_file in news_dir.rglob('*.parquet'):
        total_files += 1
        
        # Parse file path
        parts = parquet_file.parts
        source = parts[2] if len(parts) > 2 else 'Unknown'
        year_folder = int(parts[3]) if len(parts) > 3 else None
        month_file = int(parquet_file.stem) if len(parts) > 4 else None
        
        # Read data
        df = pd.read_parquet(parquet_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        total_records += len(df)
        
        # Analyze data distribution
        records_by_month = df.groupby([df['timestamp'].dt.year, df['timestamp'].dt.month]).size()
        
        print(f"\n📄 {parquet_file.relative_to('data')}")
        print(f"   Fonte: {source}")
        print(f"   Organização: {year_folder}/{month_file:02d}.parquet")
        print(f"   Total registros: {len(df)}")
        print(f"   Range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"   Distribuição por mês:")
        
        for (year, month), count in records_by_month.items():
            is_correct_location = (year == year_folder and month == month_file)
            status = "✓" if is_correct_location else "⚠️"
            print(f"     {status} {year}-{month:02d}: {count} registros")
            
            if not is_correct_location:
                issues.append({
                    'file': str(parquet_file.relative_to('data')),
                    'expected': f"{year_folder}/{month_file:02d}",
                    'actual_year': year,
                    'actual_month': month,
                    'count': count
                })
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 RESUMO:")
    print(f"   Total de arquivos: {total_files}")
    print(f"   Total de registros: {total_records}")
    print(f"   Problemas encontrados: {len(issues)}")
    
    if issues:
        print(f"\n⚠️  PROBLEMAS DE PARTICIONAMENTO:")
        for issue in issues:
            print(f"   • {issue['file']}")
            print(f"     → Contém {issue['count']} registros de {issue['actual_year']}-{issue['actual_month']:02d}")
            print(f"     → Deveria estar em {issue['actual_year']}/{issue['actual_month']:02d}.parquet")
    
    return issues

def analyze_impact():
    """Analisa o impacto dos problemas de particionamento"""
    print(f"\n{'='*60}")
    print("🎯 ANÁLISE DE IMPACTO:\n")
    
    impacts = {
        'query_performance': {
            'severity': 'BAIXO',
            'description': 'Queries ainda funcionam, mas podem precisar ler mais arquivos',
            'example': 'SELECT * FROM news WHERE timestamp >= 2025-09-01 AND timestamp < 2025-10-01'
        },
        'storage_organization': {
            'severity': 'MÉDIO',
            'description': 'Dados de meses diferentes no mesmo arquivo prejudica organização',
            'example': 'Arquivo 2025/11.parquet contém dados de setembro'
        },
        'data_retention': {
            'severity': 'BAIXO',
            'description': 'Políticas de retenção podem não funcionar corretamente',
            'example': 'Remoção de dados antigos pode afetar arquivos com dados recentes'
        },
        'backup_efficiency': {
            'severity': 'BAIXO',
            'description': 'Backups incrementais podem ser menos eficientes',
            'example': 'Arquivo modificado mesmo com dados antigos'
        }
    }
    
    for category, impact in impacts.items():
        print(f"📌 {category.replace('_', ' ').upper()}: {impact['severity']}")
        print(f"   → {impact['description']}")
        print(f"   → Exemplo: {impact['example']}")
        print()

def propose_solution():
    """Propõe soluções para o problema"""
    print(f"{'='*60}")
    print("💡 SOLUÇÕES PROPOSTAS:\n")
    
    solutions = [
        {
            'name': 'Opção 1: Particionar por mês dos DADOS (Recomendado)',
            'pros': [
                'Dados sempre no local correto',
                'Melhor performance de queries por período',
                'Facilita manutenção e limpeza',
                'Alinhado com a semântica dos dados'
            ],
            'cons': [
                'Dados novos de meses antigos vão para arquivos antigos',
                'Pode criar muitos arquivos pequenos se houver fetch histórico'
            ],
            'implementation': 'Usar timestamp dos dados para determinar o path'
        },
        {
            'name': 'Opção 2: Particionar por FONTE apenas (Simples)',
            'pros': [
                'Simplicidade extrema',
                'Um único arquivo por fonte',
                'Fácil de gerenciar'
            ],
            'cons': [
                'Arquivos podem crescer muito',
                'Queries por período menos eficientes',
                'Dificulta retenção de dados antigos'
            ],
            'implementation': 'data/news/{source}/all_data.parquet'
        },
        {
            'name': 'Opção 3: Manter como está (Status Quo)',
            'pros': [
                'Não requer mudanças',
                'Sistema funciona adequadamente'
            ],
            'cons': [
                'Incoerência semântica',
                'Possível confusão futura',
                'Queries por período podem ser menos eficientes'
            ],
            'implementation': 'Nenhuma ação'
        }
    ]
    
    for i, solution in enumerate(solutions, 1):
        print(f"{i}. {solution['name']}")
        print(f"   ✓ Vantagens:")
        for pro in solution['pros']:
            print(f"     • {pro}")
        print(f"   ✗ Desvantagens:")
        for con in solution['cons']:
            print(f"     • {con}")
        print(f"   🔧 Implementação: {solution['implementation']}")
        print()

if __name__ == "__main__":
    issues = analyze_news_partitioning()
    analyze_impact()
    propose_solution()
    
    print(f"{'='*60}")
    print("\n🎯 RECOMENDAÇÃO FINAL:")
    print("   Para RSS/News: Usar Opção 1 (particionar por mês dos DADOS)")
    print("   Para Market Data: Manter estrutura atual (sem data no path)")
    print("\n   Razão: News tem fetch incremental frequente do mês corrente,")
    print("   enquanto market data pode ter fetch histórico de qualquer período.")
    print(f"{'='*60}\n")