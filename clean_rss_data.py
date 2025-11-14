#!/usr/bin/env python3
"""
Script para limpar dados RSS (uso opcional)
"""
import os
import shutil
from pathlib import Path

def clean_rss_data():
    """Remove todos os dados RSS salvos"""
    print("=== Limpeza de Dados RSS ===\n")
    
    news_dir = Path("data/news")
    
    if news_dir.exists():
        print(f"📁 Diretório encontrado: {news_dir}")
        
        # Listar o que será removido
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(news_dir):
            for file in files:
                file_path = Path(root) / file
                size = file_path.stat().st_size / 1024
                total_size += size
                file_count += 1
        
        print(f"   • {file_count} arquivos ({total_size:.1f} KB)")
        
        confirm = input(f"\n⚠️  Deseja REMOVER todos os dados RSS? [y/N]: ")
        if confirm.lower() in ['y', 'yes', 's', 'sim']:
            shutil.rmtree(news_dir)
            print(f"✅ Dados RSS removidos com sucesso!")
            
            # Recrear estrutura básica
            news_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Diretório recreado: {news_dir}")
        else:
            print("❌ Operação cancelada.")
    else:
        print("📂 Nenhum dado RSS encontrado.")

if __name__ == "__main__":
    clean_rss_data()