import os
import xml.etree.ElementTree as ET
import shutil
import pandas as pd

# =====================================================================
# 1. CONFIGURAÇÃO DOS CAMINHOS DE PASTAS
# =====================================================================
PASTA_ENTRADA = "entrada"
PASTA_PEDIDOS = "pedidos"
PASTA_SAIDA = "saida"
PASTA_PROCESSADOS = "processados"

# Garante que as pastas existam. Se não existirem, o Python cria para você.
for pasta in [PASTA_ENTRADA, PASTA_PEDIDOS, PASTA_SAIDA, PASTA_PROCESSADOS]:
    if not os.path.exists(pasta):
        os.makedirs(pasta)

# =====================================================================
# 2. FUNÇÃO PARA EXTRAIR DADOS DE UM XML DE NF-e
# =====================================================================
def extrair_dados_xml(caminho_xml):
    """
    Abre o arquivo XML da NF-e e extrai os dados principais.
    Nota: O XML da NF-e usa um sistema de 'namespaces' (aquela URL no início das tags).
    """
    try:
        tree = ET.parse(caminho_xml)
        root = tree.getroot()
        
        # O XML da NF-e geralmente usa o namespace padrão da SEFAZ
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Procurando as tags específicas usando o namespace
        # (Se o seu XML não tiver namespace, use root.find('.//chNFe').text)
        chave_acesso = root.find('.//ns:chNFe', ns)
        if chave_acesso is None:
            # Caso de contingência ou outra tag de chave
            chave_acesso = root.find('.//ns:infProt/ns:chNFe', ns)
            
        cnpj_emissor = root.find('.//ns:emit/ns:CNPJ', ns)
        valor_total = root.find('.//ns:ICMSTot/ns:vNF', ns)
        numero_nota = root.find('.//ns:ide/ns:nNF', ns)
        
        # Extraindo o texto de dentro das tags (se encontradas)
        dados = {
            "Chave_Acesso": chave_acesso.text if chave_acesso is not None else "Não encontrada",
            "Numero_Nota": numero_nota.text if numero_nota is not None else "Não encontrado",
            "CNPJ_Emissor": cnpj_emissor.text if cnpj_emissor is not None else "Não encontrado",
            "Valor_Nota": float(valor_total.text) if valor_total is not None else 0.0,
            "Nome_Arquivo": os.path.basename(caminho_xml)
        }
        return dados
        
    except Exception as e:
        print(f"Erro ao ler o arquivo {caminho_xml}: {e}")
        return None

# =====================================================================
# 3. PROCESSO PRINCIPAL (FLUXO DO SCRIPT)
# =====================================================================
def executar_conciliacao():
    print("Iniciando o processo de conciliação...")
    
    # 3.1. Ler todos os XMLs da pasta 'entrada'
    notas_extraidas = []
    arquivos_xml = [f for f in os.listdir(PASTA_ENTRADA) if f.endswith('.xml')]
    
    if not arquivos_xml:
        print("Nenhum arquivo XML encontrado na pasta 'entrada'. Adicione arquivos lá para testar!")
        return

    for arquivo in arquivos_xml:
        caminho_completo = os.path.join(PASTA_ENTRADA, arquivo)
        dados = extrair_dados_xml(caminho_completo)
        
        if dados:
            notas_extraidas.append(dados)
            # Move o arquivo processado para a pasta 'processados' para não ler de novo na próxima rodada
            shutil.move(caminho_completo, os.path.join(PASTA_PROCESSADOS, arquivo))

    # Transforma as notas extraídas em uma tabela (DataFrame do Pandas)
    df_notas = pd.DataFrame(notas_extraidas)
    print(f"{len(df_notas)} notas fiscais lidas com sucesso.")

    # 3.2. Carregar a planilha de Pedidos de Compra
    caminho_pedidos = os.path.join(PASTA_PEDIDOS, "pedidos_compra.xlsx")
    if not os.path.exists(caminho_pedidos):
        print(f"Erro: Planilha de pedidos não encontrada em '{caminho_pedidos}'!")
        # Vamos criar um arquivo de exemplo se ele não existir, para te ajudar no primeiro teste
        exemplo_pedidos = pd.DataFrame({
            "CNPJ_Fornecedor": ["12345678000199"],  # Substitua pelo CNPJ real das suas notas de teste
            "Valor_Esperado": [1500.00]
        })
        exemplo_pedidos.to_excel(caminho_pedidos, index=False)
        print(f"Criamos uma planilha de pedidos exemplo em '{caminho_pedidos}'. Ajuste os valores lá.")
        return

    df_pedidos = pd.read_excel(caminho_pedidos)
    
    # Garante que os CNPJs sejam tratados como texto para não dar erro na comparação
    df_notas["CNPJ_Emissor"] = df_notas["CNPJ_Emissor"].astype(str).str.strip()
    df_pedidos["CNPJ_Fornecedor"] = df_pedidos["CNPJ_Fornecedor"].astype(str).str.strip()

    # 3.3. Conciliação (Cruzamento de dados)
    # Fazemos um 'merge' (como um PROCV do Excel) unindo pelo CNPJ
    df_conciliado = pd.merge(
        df_notas, 
        df_pedidos, 
        left_on="CNPJ_Emissor", 
        right_on="CNPJ_Fornecedor", 
        how="left"
    )

    # Criamos uma coluna de status para validar os valores
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

    # 3.4. Salvar o resultado
    caminho_relatorio = os.path.join(PASTA_SAIDA, "relatorio_conciliacao.xlsx")
    df_conciliado.to_excel(caminho_relatorio, index=False)
    
    print("\n--- PROCESSO CONCLUÍDO ---")
    print(f"Relatório gerado em: {caminho_relatorio}")
    print(df_conciliado[["Numero_Nota", "Valor_Nota", "Status_Conciliacao"]])

# Executa o script
if __name__ == "__main__":
    executar_conciliacao()