#!/usr/bin/env python3
"""
Implementação melhorada do particionamento de news data
Particiona por ano/mês baseado no TIMESTAMP dos dados, não na data atual
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timezone
import hashlib


class SmartNewsPartitioner:
    """
    Particionador inteligente para news data
    Organiza dados por fonte e período baseado no timestamp dos dados
    """
    
    def __init__(self, base_path: str = "data/news"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def store_news_data(self, df: pd.DataFrame, source: str) -> Dict[str, Path]:
        """
        Armazena news data particionado por período dos DADOS (não data atual)
        
        Returns:
            Dict com mapeamento {year_month: file_path}
        """
        df = df.copy()
        
        # Garantir timestamp em UTC
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        # Adicionar metadados
        if 'source' not in df.columns:
            df['source'] = source
        if 'created_at' not in df.columns:
            df['created_at'] = datetime.now(timezone.utc)
        
        # Calcular hash para deduplicação
        if 'link' in df.columns and 'timestamp' in df.columns:
            df['content_hash'] = self._calculate_hash(df, ['link', 'timestamp'])
        
        # Particionar por ano/mês baseado no timestamp dos dados
        df['_year'] = df['timestamp'].dt.year
        df['_month'] = df['timestamp'].dt.month
        
        saved_files = {}
        
        # Processar cada partição separadamente
        for (year, month), group_df in df.groupby(['_year', '_month']):
            # Remover colunas auxiliares
            group_df = group_df.drop(columns=['_year', '_month'])
            
            # Determinar path baseado nos dados
            file_path = self._get_file_path(source, int(year), int(month))
            
            # Merge com dados existentes
            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'], utc=True)
                
                # Combinar e deduplicate
                combined_df = pd.concat([existing_df, group_df], ignore_index=True)
                combined_df = self._deduplicate(combined_df)
                combined_df = combined_df.sort_values('timestamp')
            else:
                combined_df = self._deduplicate(group_df)
            
            # Salvar
            combined_df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
            
            key = f"{year}-{month:02d}"
            saved_files[key] = file_path
            
            print(f"✓ Saved {len(combined_df)} records to {file_path.relative_to(self.base_path.parent)}")
        
        return saved_files
    
    def _get_file_path(self, source: str, year: int, month: int) -> Path:
        """Gera path do arquivo baseado no período dos dados"""
        # Sanitizar nome da fonte
        clean_source = source.replace('/', '_').replace(' ', '_').replace('-', '_')
        
        # Estrutura: data/news/{source}/{year}/{month}.parquet
        file_path = self.base_path / clean_source / str(year) / f"{month:02d}.parquet"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        return file_path
    
    def _calculate_hash(self, df: pd.DataFrame, columns: List[str]) -> pd.Series:
        """Calcula hash para deduplicação"""
        hash_data = df[columns].astype(str).apply(lambda x: '|'.join(x), axis=1)
        return hash_data.apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    
    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicatas baseado em link + timestamp"""
        dedup_cols = ['link', 'timestamp']
        existing_cols = [col for col in dedup_cols if col in df.columns]
        
        if existing_cols:
            df = df.drop_duplicates(subset=existing_cols, keep='last')
        
        return df
    
    def reorganize_existing_data(self, source: str = None, dry_run: bool = True) -> Dict[str, int]:
        """
        Reorganiza dados existentes para o formato correto
        
        Args:
            source: Reorganizar apenas esta fonte (None = todas)
            dry_run: Se True, apenas mostra o que seria feito
        """
        print(f"\n{'='*60}")
        print(f"{'DRY RUN - ' if dry_run else ''}REORGANIZAÇÃO DE DADOS")
        print(f"{'='*60}\n")
        
        stats = {'files_read': 0, 'files_created': 0, 'records_moved': 0}
        
        # Encontrar todos os arquivos parquet
        pattern = f"*/{source}/**/*.parquet" if source else "**/*.parquet"
        existing_files = list(self.base_path.glob(pattern))
        
        for file_path in existing_files:
            stats['files_read'] += 1
            
            # Parse source do path
            relative_path = file_path.relative_to(self.base_path)
            file_source = str(relative_path.parts[0])
            
            print(f"📄 Processando: {relative_path}")
            
            # Ler dados
            df = pd.read_parquet(file_path)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            
            # Analisar distribuição
            distribution = df.groupby([df['timestamp'].dt.year, df['timestamp'].dt.month]).size()
            
            print(f"   Distribuição encontrada:")
            for (year, month), count in distribution.items():
                print(f"     • {year}-{month:02d}: {count} registros")
            
            # Se dry_run, apenas reportar
            if dry_run:
                print(f"   [DRY RUN] Seria reorganizado em {len(distribution)} arquivo(s)")
                continue
            
            # Reorganizar dados
            saved_files = self.store_news_data(df, file_source)
            stats['files_created'] += len(saved_files)
            stats['records_moved'] += len(df)
            
            # Remover arquivo antigo se tudo deu certo
            # (Comentado por segurança - descomente após validação)
            # file_path.unlink()
            # print(f"   ✓ Arquivo antigo removido: {relative_path}")
        
        print(f"\n{'='*60}")
        print("📊 ESTATÍSTICAS:")
        print(f"   Arquivos lidos: {stats['files_read']}")
        print(f"   Arquivos criados: {stats['files_created']}")
        print(f"   Registros movidos: {stats['records_moved']}")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN - Nenhuma alteração foi feita")
            print(f"   Execute com dry_run=False para aplicar mudanças")
        
        return stats


# Exemplo de uso
if __name__ == "__main__":
    import sys
    
    partitioner = SmartNewsPartitioner()
    
    print("=== SMART NEWS PARTITIONER ===\n")
    print("Este script reorganiza os dados RSS para o formato correto")
    print("baseado no TIMESTAMP dos dados, não na data de escrita.\n")
    
    # Primeiro: dry run
    print("Executando DRY RUN (nenhuma alteração será feita)...\n")
    stats = partitioner.reorganize_existing_data(dry_run=True)
    
    if stats['files_read'] > 0:
        print(f"\n{'='*60}")
        response = input("Deseja aplicar as mudanças? [y/N]: ")
        
        if response.lower() in ['y', 'yes', 's', 'sim']:
            print("\nAplicando reorganização...\n")
            stats = partitioner.reorganize_existing_data(dry_run=False)
            print("\n✅ Reorganização concluída!")
        else:
            print("\n❌ Operação cancelada.")
    else:
        print("\n✅ Nenhum dado para reorganizar.")