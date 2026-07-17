# 📑 Conciliador Automático de Notas Fiscais (XML e PDF)

Este projeto foi desenvolvido para automatizar o processo de conciliação financeira entre Notas Fiscais (tanto em formato XML quanto em PDFs de DANFE) e a planilha de Pedidos de Compra interna da empresa.

## 🚀 Funcionalidades
- **Leitura de XML:** Extração automatizada de chave de acesso, CNPJ emissor, número da nota e valor (com tratamento para evitar erros de namespace).
- **Leitura de PDF:** Extração de texto usando Regex para identificar CNPJs, valores monetários totais e números de notas fiscais.
- **Conciliação Inteligente:** Cruzamento automático de dados com base no CNPJ do fornecedor.
- **Análise de Divergências:** Identifica se o valor da nota está batendo, se é maior ou menor que o pedido de compra, gerando o cálculo exato da diferença.
- **Relatório em Excel:** Exporta um painel limpo em `.xlsx` na pasta de saída.

## 🛠️ Tecnologias Utilizadas
- Python 3.13
- Pandas (Tratamento e cruzamento de dados)
- Pdfplumber (Extração de texto de arquivos PDF)
- Openpyxl (Geração dos relatórios Excel)

## 📦 Como Executar o Projeto
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt