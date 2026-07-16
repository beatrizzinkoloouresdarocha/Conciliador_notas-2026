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
        tree = ET.parse(caminho_xml)
        root = tree.getroot()
        
        # Remove o namespace para facilitar a busca em qualquer tipo de XML (NF-e ou NFS-e)
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
        xml_sem_ns = re.sub(r'\sxmlns="[^"]+"', '', xml_str, count=1)
        xml_sem_ns = re.sub(r'\sxmlns:[^=]+="[^"]+"', '', xml_sem_ns)
        root = ET.fromstring(xml_sem_ns)
        
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

    # Filtra para ler apenas XML e PDF reais, ignorando planilhas Excel caso estejam lá sem querer
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

    # Transforma as notas extraídas em tabela
    df_notas = pd.DataFrame(notas_extraidas)
    print(f"\n{len(df_notas)} notas lidas com sucesso.")

    # 4.2. Carregar a planilha de Pedidos de Compra
    caminho_pedidos = os.path.join(PASTA_PEDIDOS, "pedidos_compra.xlsx")
    if not os.path.exists(caminho_pedidos):
        print(f"Erro: Planilha de pedidos não encontrada em '{caminho_pedidos}'.")
        return

    df_pedidos = pd.read_excel(caminho_pedidos)
    
    # --- MAPEAMENTO E PADRONIZAÇÃO DE COLUNAS DA PLANILHA REAL ---
    # Se as colunas estiverem no formato em português do seu arquivo real, renomeamos para o código entender:
    colunas_mapa = {
        "CNPJ do Fornecedor": "CNPJ_Fornecedor",
        "Valor do Pedido (R$)": "Valor_Esperado"
    }
    df_pedidos = df_pedidos.rename(columns=colunas_mapa)

    # Garante que as colunas necessárias existam
    if "CNPJ_Fornecedor" not in df_pedidos.columns or "Valor_Esperado" not in df_pedidos.columns:
        print("Erro: A planilha de pedidos precisa conter as colunas de CNPJ e Valor do Pedido.")
        return
    
    # Padroniza os CNPJs para comparação
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

    # Função para validar valores
    def verificar_status(row):
        if pd.isna(row["Valor_Esperado"]):
            return "Atenção: Pedido de compra não localizado!"
        elif row["Valor_Nota"] == row["Valor_Esperado"]:
            return "Conciliado (Valores Batem!)"
        elif row["Valor_Nota"] > row["Valor_Esperado"]:
            diferenca = row["Valor_Nota"] - row["Valor_Esperado"]
            return f"Divergência (Pedido: R$ {row['Valor_Esperado']:,.2f} | Nota: R$ {row['Valor_Nota']:,.2f})"
        else:
            return f"Divergência (Pedido: R$ {row['Valor_Esperado']:,.2f} | Nota: R$ {row['Valor_Nota']:,.2f})"

    df_conciliado["Status_Conciliacao"] = df_conciliado.apply(verificar_status, axis=1)

    # 4.4. Salvar o resultado
    if not os.path.exists(PASTA_SAIDA):
        os.makedirs(PASTA_SAIDA)
        
    caminho_relatorio = os.path.join(PASTA_SAIDA, "resultado_financeiro.xlsx")
    df_conciliado.to_excel(caminho_relatorio, index=False)
    
    print("\n--- PROCESSO CONCLUÍDO ---")
    print(f"Relatório gerado em: {caminho_relatorio}")
    print(df_conciliado[["Nome_Arquivo", "Tipo_Arquivo", "Valor_Nota", "Status_Conciliacao"]])

# Executa o script
if __name__ == "__main__":
    executar_conciliacao()