import os
import xml.etree.ElementTree as ET
import shutil
import re
import pandas as pd
import pdfplumber

# =====================================================================
# 1. CONFIGURAÇÃO DOS CAMINHOS DE PASTAS
# =====================================================================
PASTA_ENTRADA = "entrada"
PASTA_PEDIDOS = "pedidos"
PASTA_SAIDA = "saida"
PASTA_PROCESSADOS = "processados"

# Garante que as pastas existam.
for pasta in [PASTA_ENTRADA, PASTA_PEDIDOS, PASTA_SAIDA, PASTA_PROCESSADOS]:
    if not os.path.exists(pasta):
        os.makedirs(pasta)

# =====================================================================
# 2. FUNÇÃO PARA EXTRAIR DADOS DE UM XML DE NF-e
# =====================================================================
def extrair_dados_xml(caminho_xml):
    try:
        # Lemos o arquivo como texto puro primeiro para limpar problemas de namespaces/prefixos
        with open(caminho_xml, 'r', encoding='utf-8') as f:
             xml_conteudo = f.read()
        
        # Remove qualquer prefixo de namespace (ex: <ns2:det> vira <det>) para evitar o erro 'unbound prefix'
        xml_limpo = re.sub(r'<\/?\w+:', '<', xml_conteudo)
        # Remove declarações de namespaces complexas
        xml_limpo = re.sub(r'\sxmlns:[^=]+="[^"]+"', '', xml_limpo)
        xml_limpo = re.sub(r'\sxmlns="[^"]+"', '', xml_limpo)
        
        root = ET.fromstring(xml_limpo)
        
        chave_acesso = root.find('.//chNFe')
        if chave_acesso is None:
            chave_acesso = root.find('.//infProt/chNFe')
            
        cnpj_emissor = root.find('.//emit/CNPJ')
        valor_total = root.find('.//ICMSTot/vNF')
        
        # Tentativa para NFS-e (Serviço) caso não ache vNF
        if valor_total is None:
            valor_total = root.find('.//Valores/ValorServicos')
            
        numero_nota = root.find('.//ide/nNF')
        if numero_nota is None:
            numero_nota = root.find('.//IdentificacaoRps/Numero')

        dados = {
            "Chave_Acesso": chave_acesso.text if chave_acesso is not None else "N/A",
            "Numero_Nota": numero_nota.text if numero_nota is not None else "Não encontrado",
            "CNPJ_Emissor": cnpj_emissor.text if cnpj_emissor is not None else "Não encontrado",
            "Valor_Nota": float(valor_total.text) if valor_total is not None else 0.0,
            "Nome_Arquivo": os.path.basename(caminho_xml),
            "Tipo_Arquivo": "XML"
        }
        return dados
    except Exception as e:
        print(f"Erro ao ler o arquivo XML {caminho_xml}: {e}")
        return None

# =====================================================================
# 3. FUNÇÃO PARA EXTRAIR DADOS DE UM PDF
# =====================================================================
def extrair_dados_pdf(caminho_pdf):
    try:
        texto_completo = ""
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + "\n"
        
        # Se o PDF for uma imagem (texto vazio), avisa o usuário
        if not texto_completo.strip():
            print(f"Aviso: O PDF {os.path.basename(caminho_pdf)} parece ser uma imagem digitalizada e não pôde ser lido.")
            return None

        # Procurando o CNPJ usando Expressão Regular
        padrao_cnpj = r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14})"
        cnpjs_encontrados = re.findall(padrao_cnpj, texto_completo)
        
        cnpj_limpo = "Não encontrado"
        if cnpjs_encontrados:
            cnpj_limpo = re.sub(r"\D", "", cnpjs_encontrados[0])

        # Busca de valor muito mais flexível (procura palavras-chave próximas a valores monetários)
        padrao_valor = r"(?:VALOR TOTAL|TOTAL DA NOTA|VALOR LÍQUIDO|VALOR LIQUIDO|TOTAL DE SERVIÇOS|TOTAL DOS SERVIÇOS|VALOR COBRADO|VALOR DA NOTA|TOTAL.*?R\$|LIQUIDO.*?R\$).*?(\d{1,3}(?:\.\d{3})*,\d{2})"
        valores_encontrados = re.findall(padrao_valor, texto_completo, re.IGNORECASE)
        
        # Busca secundária caso o padrão principal não encontre nada
        if not valores_encontrados:
            # Procura por qualquer valor monetário "R$ XX,XX" ou "R$XX,XX"
            valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto_completo, re.IGNORECASE)

        valor_nota = 0.0
        if valores_encontrados:
            valor_texto = valores_encontrados[0].replace(".", "").replace(",", ".")
            valor_nota = float(valor_texto)

        # Localizando o Número da Nota Fiscal
        padrao_numero_nota = r"(?:Nº|NÚMERO|NUMERO|NOTA|RPS)\s*:?\s*(\d+)"
        numeros_encontrados = re.findall(padrao_numero_nota, texto_completo, re.IGNORECASE)
        numero_nota = "Não encontrado"
        if numeros_encontrados:
            numero_nota = numeros_encontrados[0]

        dados = {
            "Chave_Acesso": "N/A (PDF)",
            "Numero_Nota": numero_nota,
            "CNPJ_Emissor": cnpj_limpo,
            "Valor_Nota": valor_nota,
            "Nome_Arquivo": os.path.basename(caminho_pdf),
            "Tipo_Arquivo": "PDF"
        }
        return dados
    except Exception as e:
        print(f"Erro ao ler o arquivo PDF {caminho_pdf}: {e}")
        return None

# =====================================================================
# 4. PROCESSO PRINCIPAL (FLUXO DO SCRIPT)
# =====================================================================
def executar_conciliacao():
    print("Iniciando o processo de conciliação (XML e PDF)...")
    
    # 4.1. Ler todos os arquivos da pasta 'entrada' (XML e PDF)
    notas_extraidas = []
    arquivos = os.listdir(PASTA_ENTRADA)
    
    if not arquivos:
        print("Nenhum arquivo XML ou PDF encontrado na pasta 'entrada'. Adicione arquivos lá para testar!")
        return

    arquivos_validos = [arq for arq in arquivos if arq.lower().endswith(('.xml', '.pdf'))]

    if not arquivos_validos:
        print("Nenhum arquivo XML ou PDF válido encontrado na pasta 'entrada'.")
        return

    for arquivo in arquivos_validos:
        caminho_completo = os.path.join(PASTA_ENTRADA, arquivo)
        dados = None
        
        if arquivo.lower().endswith('.xml'):
            print(f"Lendo XML: {arquivo}")
            dados = extrair_dados_xml(caminho_completo)
        elif arquivo.lower().endswith('.pdf'):
            print(f"Lendo PDF: {arquivo}")
            dados = extrair_dados_pdf(caminho_completo)
            
        if dados:
            notas_extraidas.append(dados)
            shutil.move(caminho_completo, os.path.join(PASTA_PROCESSADOS, arquivo))
        else:
            print(f"Aviso: Não foi possível ler dados úteis de '{arquivo}'.")

    if not notas_extraidas:
        print("Nenhum dado pôde ser extraído das notas fornecidas.")
        return

    df_notas = pd.DataFrame(notas_extraidas)
    print(f"\n{len(df_notas)} notas lidas com sucesso.")

    # 4.2. Carregar a planilha de Pedidos de Compra
    caminho_pedidos = os.path.join(PASTA_PEDIDOS, "pedidos_compra.xlsx")
    if not os.path.exists(caminho_pedidos):
        print(f"Erro: Planilha de pedidos não encontrada em '{caminho_pedidos}'.")
        return

    df_pedidos = pd.read_excel(caminho_pedidos)
    
    # --- MAPEAMENTO E PADRONIZAÇÃO DE COLUNAS ---
    colunas_mapa = {
        "CNPJ do Fornecedor": "CNPJ_Fornecedor",
        "Valor do Pedido (R$)": "Valor_Esperado"
    }
    df_pedidos = df_pedidos.rename(columns=colunas_mapa)

    if "CNPJ_Fornecedor" not in df_pedidos.columns or "Valor_Esperado" not in df_pedidos.columns:
        print("Erro: A planilha de pedidos precisa conter as colunas de CNPJ e Valor do Pedido.")
        return
    
    df_notas["CNPJ_Emissor"] = df_notas["CNPJ_Emissor"].astype(str).str.strip().str.replace(r"\D", "", regex=True)
    df_pedidos["CNPJ_Fornecedor"] = df_pedidos["CNPJ_Fornecedor"].astype(str).str.strip().str.replace(r"\D", "", regex=True)

    # 4.3. Conciliação (Cruzamento de dados)
    df_conciliado = pd.merge(
        df_notas, 
        df_pedidos, 
        left_on="CNPJ_Emissor", 
        right_on="CNPJ_Fornecedor", 
        how="left"
    )

    # Nova lógica melhorada de verificação com cálculo da diferença
    def verificar_status(row):
        if pd.isna(row["Valor_Esperado"]):
            return "Atenção: Pedido de compra não localizado!", 0.0
        
        diferenca = round(row["Valor_Nota"] - row["Valor_Esperado"], 2)
        
        if diferenca == 0.0:
            return "Conciliado (Valores Batem!)", 0.0
        elif diferenca > 0.0:
            return f"Divergência: Nota MAIOR que pedido", diferenca
        else:
            return f"Divergência: Nota MENOR que pedido", diferenca

    # Aplica a função e separa o Status e o Valor da Diferença em duas colunas novas
    resultados_status = df_conciliado.apply(verificar_status, axis=1)
    df_conciliado["Status_Conciliacao"] = [res[0] for res in resultados_status]
    df_conciliado["Valor_Diferenca"] = [res[1] for res in resultados_status]

    # Organiza e limpa o DataFrame para salvar no Excel de forma organizada
    df_relatorio_final = df_conciliado[[
        "Numero_Nota", "CNPJ_Emissor", "Tipo_Arquivo", 
        "Valor_Nota", "Valor_Esperado", "Valor_Diferenca", 
        "Status_Conciliacao", "Nome_Arquivo", "Chave_Acesso"
    ]].rename(columns={
        "Numero_Nota": "Número da Nota",
        "CNPJ_Emissor": "CNPJ Emitente",
        "Tipo_Arquivo": "Tipo",
        "Valor_Nota": "Valor da Nota (R$)",
        "Valor_Esperado": "Valor do Pedido (R$)",
        "Valor_Diferenca": "Diferença (R$)",
        "Status_Conciliacao": "Status da Conciliação",
        "Nome_Arquivo": "Arquivo Original"
    })

    # 4.4. Salvar o resultado na pasta 'saida'
    caminho_relatorio = os.path.join(PASTA_SAIDA, "resultado_financeiro.xlsx")
    df_relatorio_final.to_excel(caminho_relatorio, index=False)
    
    print("\n--- PROCESSO CONCLUÍDO ---")
    print(f"Relatório detalhado gerado com sucesso em: {caminho_relatorio}")
    print(df_relatorio_final[["Número da Nota", "Valor da Nota (R$)", "Status da Conciliação"]])

if __name__ == "__main__":
    executar_conciliacao()