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
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
        
        chave_acesso = root.find('.//ns:chNFe', ns)
        if chave_acesso is None:
            chave_acesso = root.find('.//ns:infProt/ns:chNFe', ns)
            
        cnpj_emissor = root.find('.//ns:emit/ns:CNPJ', ns)
        valor_total = root.find('.//ns:ICMSTot/ns:vNF', ns)
        numero_nota = root.find('.//ns:ide/ns:nNF', ns)
        
        dados = {
            "Chave_Acesso": chave_acesso.text if chave_acesso is not None else "Não encontrada",
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
    """
    Abre o PDF, extrai o texto e tenta encontrar o CNPJ e o Valor Total da nota.
    """
    try:
        texto_completo = ""
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + "\n"
        
        # Procurando o CNPJ usando Expressão Regular
        padrao_cnpj = r"(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}|\d{14})"
        cnpjs_encontrados = re.findall(padrao_cnpj, texto_completo)
        
        cnpj_limpo = "Não encontrado"
        if cnpjs_encontrados:
            cnpj_limpo = re.sub(r"\D", "", cnpjs_encontrados[0])

        # Procurando o Valor Total da Nota (Refinado para evitar falsos positivos)
        padrao_valor = r"(?:VALOR TOTAL|TOTAL DA NOTA|VALOR LÍQUIDO|VALOR LIQUIDO|TOTAL DE SERVIÇOS|TOTAL DOS SERVIÇOS).*?(\d{1,3}(?:\.\d{3})*,\d{2})"
        valores_encontrados = re.findall(padrao_valor, texto_completo, re.IGNORECASE)
        
        valor_nota = 0.0
        if valores_encontrados:
            valor_texto = valores_encontrados[0].replace(".", "").replace(",", ".")
            valor_nota = float(valor_texto)

        # Localizando o Número da Nota Fiscal
        padrao_numero_nota = r"Nº\s*(\d+)|NÚMERO\s*(\d+)|NUMERO\s*(\d+)"
        numeros_encontrados = re.findall(padrao_numero_nota, texto_completo, re.IGNORECASE)
        numero_nota = "Não encontrado"
        if numeros_encontrados:
            lista_numeros = [num for tupla in numeros_encontrados for num in tupla if num]
            if lista_numeros:
                numero_nota = lista_numeros[0]

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

    for arquivo in arquivos:
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
            # Move o arquivo processado para não duplicar na próxima rodada
            shutil.move(caminho_completo, os.path.join(PASTA_PROCESSADOS, arquivo))

    if not notas_extraidas:
        print("Nenhum dado pôde ser extraído das notas fornecidas.")
        return

    # Transforma as notas extraídas em tabela
    df_notas = pd.DataFrame(notas_extraidas)
    print(f"\n{len(df_notas)} notas lidas com sucesso.")

    # 4.2. Carregar a planilha de Pedidos de Compra
    caminho_pedidos = os.path.join(PASTA_PEDIDOS, "pedidos_compra.xlsx")
    if not os.path.exists(caminho_pedidos):
        # Cria uma de exemplo se não existir
        exemplo_pedidos = pd.DataFrame({
            "CNPJ_Fornecedor": ["12345678000199"],
            "Valor_Esperado": [1500.00]
        })
        exemplo_pedidos.to_excel(caminho_pedidos, index=False)
        print(f"Criamos uma planilha de pedidos exemplo em '{caminho_pedidos}'. Ajuste os valores lá.")
        return

    df_pedidos = pd.read_excel(caminho_pedidos)
    
    # Padroniza os CNPJs para comparação
    df_notas["CNPJ_Emissor"] = df_notas["CNPJ_Emissor"].astype(str).str.strip()
    df_pedidos["CNPJ_Fornecedor"] = df_pedidos["CNPJ_Fornecedor"].astype(str).str.strip()

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
            return "Pedido não encontrado no sistema"
        elif row["Valor_Nota"] == row["Valor_Esperado"]:
            return "Conciliado (Valor Correto)"
        elif row["Valor_Nota"] > row["Valor_Esperado"]:
            return "Divergência: Valor cobrado maior que o pedido"
        else:
            return "Divergência: Valor cobrado menor que o pedido"

    df_conciliado["Status_Conciliacao"] = df_conciliado.apply(verificar_status, axis=1)

    # 4.4. Salvar o resultado
    caminho_relatorio = os.path.join(PASTA_SAIDA, "relatorio_conciliacao.xlsx")
    df_conciliado.to_excel(caminho_relatorio, index=False)
    
    print("\n--- PROCESSO CONCLUÍDO ---")
    print(f"Relatório gerado em: {caminho_relatorio}")
    print(df_conciliado[["Nome_Arquivo", "Tipo_Arquivo", "Valor_Nota", "Status_Conciliacao"]])

# Executa o script (garantindo que não há espaços vazios no início da linha)
if __name__ == "__main__":
    executar_conciliacao()