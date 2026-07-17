import os

# Garante que a pasta 'entrada' exista no seu projeto
PASTA_ENTRADA = "entrada"
os.makedirs(PASTA_ENTRADA, exist_ok=True)

print("Iniciando a criação dos arquivos fake de teste...")

# =====================================================================
# 1. CRIAR O XML FICTÍCIO (Distribuidora de Papéis Silva)
# =====================================================================
conteudo_xml = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
    <NFe>
        <infNFe Id="NFe35260712345678000199550010000010241000010248" versao="4.00">
            <ide><nNF>1024</nNF></ide>
            <emit><CNPJ>12345678000199</CNPJ><xNome>Distribuidora de Papéis Silva Ltda</xNome></emit>
            <dest><CNPJ>99999999000199</CNPJ><xNome>Empresa da Priscila</xNome></dest>
            <det nItem="1"><prod><xProd>Papel Sulfite A4</xProd><vProd>1520.50</vProd></prod></det>
            <total><ICMSTot><vNF>1520.50</vNF></ICMSTot></total>
        </infNFe>
    </NFe>
</nfeProc>"""

with open(os.path.join(PASTA_ENTRADA, "NFe_1024_silva.xml"), "w", encoding="utf-8") as f:
    f.write(conteudo_xml)
print("✓ XML criado em: entrada/NFe_1024_silva.xml")

# =====================================================================
# 2. CRIAR O PDF FICTÍCIO (Tech Solutions Logística)
# =====================================================================
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    c = canvas.Canvas(os.path.join(PASTA_ENTRADA, "DANFE_tech_solutions.pdf"), pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 750, "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA")
    c.setFont("Helvetica", 10)
    c.drawString(50, 720, "EMISSOR: Tech Solutions Logística")
    c.drawString(50, 705, "CNPJ EMISSOR: 98.765.432/0001-88")
    c.drawString(50, 690, "Nº DA NOTA: 5590")
    c.drawString(50, 650, "DESTINATÁRIO: Empresa da Priscila")
    c.drawString(50, 560, "VALOR TOTAL DA NOTA: R$ 450,00")
    c.save()
    print("✓ PDF criado em: entrada/DANFE_tech_solutions.pdf")
except Exception as e:
    print("Erro no PDF:", e)