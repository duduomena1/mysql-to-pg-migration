#!/usr/bin/env python3
"""
Script para corrigir indentação do bloco OLD method no arquivo PG_to_PG.py
"""

import re

file_path = "pages/13_🔄_PG_to_PG.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar as linhas que precisam ser indentadas
# Procurar pela linha que tem "src_cursor = source.connection.cursor()" após o for loop
# e indentar tudo até o "except Exception as table_error:"

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    # Encontrar onde começa o bloco que precisa ser indentado
    if 'src_cursor = source.connection.cursor()' in line and start_idx is None:
        # Verificar se esta linha está com indentação de 24 espaços (já correta) ou 20
        if line.startswith(' ' * 28):  # Já indentada corretamente
            continue
        start_idx = i
    
    # Encontrar onde termina (no except Exception as table_error)
    if start_idx is not None and 'except Exception as table_error:' in line:
        end_idx = i
        break

if start_idx and end_idx:
    print(f"Encontrado bloco para indentar: linhas {start_idx+1} a {end_idx}")
    
    # Adicionar 4 espaços a cada linha entre start_idx e end_idx
    for i in range(start_idx, end_idx):
        # Pular linhas em branco
        if lines[i].strip():
            lines[i] = '    ' + lines[i]
    
    # Salvar o arquivo
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ Indentação corrigida!")
else:
    print("❌ Bloco não encontrado")
    if start_idx:
        print(f"Start: {start_idx + 1}")
    if end_idx:
        print(f"End: {end_idx + 1}")
