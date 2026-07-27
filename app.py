import streamlit as st
import fitz  # PyMuPDF
import anthropic
import io
import re

st.set_page_config(page_title="Subrayador de Manifiestos", layout="centered")

st.title("📄 Automatización: Subrayado de Manifiestos")
st.write("Sube la factura para extraer las referencias y luego sube el manifiesto para subrayarlas automáticamente.")

# 1. Configuración de la API Key
api_key = st.text_input("Ingresa tu API Key de Anthropic (Claude):", type="password")

# 2. Subida de archivos
col1, col2 = st.columns(2)
with col1:
    factura_file = st.file_uploader("1. Sube la Factura (PDF)", type=["pdf"])
with col2:
    manifiesto_file = st.file_uploader("2. Sube el Manifiesto (PDF)", type=["pdf"])

def extraer_texto_pdf(pdf_file):
    """Extrae todo el texto de un archivo PDF."""
    texto = ""
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    for page in doc:
        texto += page.get_text()
    return texto

def obtener_referencias_con_claude(texto_factura, api_key):
    """Usa Claude para extraer referencias, números de lote, etc."""
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""
    Eres un asistente de logística. Extrae de esta factura los números de referencia, 
    números de contenedor, códigos de producto o lotes que sean importantes para buscar en un manifiesto.
    Devuelve ÚNICAMENTE una lista separada por comas con los valores exactos, sin texto adicional ni explicaciones.
    
    Texto de la factura:
    {texto_factura}
    """
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    # Limpiamos la respuesta para obtener una lista de Python
    texto_respuesta = response.content[0].text
    referencias = [ref.strip() for ref in texto_respuesta.split(",") if ref.strip()]
    return referencias

def subrayar_manifiesto(manifiesto_file, referencias):
    """Busca las referencias en el manifiesto y las subraya en amarillo."""
    doc = fitz.open(stream=manifiesto_file.read(), filetype="pdf")
    
    coincidencias_totales = 0
    
    for page in doc:
        for ref in referencias:
            if len(ref) > 3:  # Evitar subrayar palabras muy cortas por error
                # Buscar la referencia en la página
                areas_encontradas = page.search_for(ref)
                for area in areas_encontradas:
                    # Añadir el resaltado amarillo
                    highlight = page.add_highlight_annot(area)
                    highlight.update()
                    coincidencias_totales += 1
                    
    # Guardar el PDF modificado en memoria
    pdf_bytes = io.BytesIO()
    doc.save(pdf_bytes)
    doc.close()
    
    return pdf_bytes.getvalue(), coincidencias_totales

# 3. Botón de Procesamiento
if st.button("🚀 Procesar y Subrayar Manifiesto"):
    if not api_key:
        st.error("Por favor, ingresa tu API Key de Anthropic.")
    elif not factura_file or not manifiesto_file:
        st.error("Por favor, sube ambos documentos (Factura y Manifiesto).")
    else:
        with st.spinner("Leyendo factura y analizando datos con IA..."):
            try:
                # Paso 1: Leer factura
                texto_factura = extraer_texto_pdf(factura_file)
                
                # Paso 2: Extraer referencias
                referencias = obtener_referencias_con_claude(texto_factura, api_key)
                st.success(f"Referencias encontradas: {', '.join(referencias)}")
                
                # Paso 3: Subrayar manifiesto
                manifiesto_file.seek(0) # Reiniciar el puntero del archivo
                pdf_modificado, coincidencias = subrayar_manifiesto(manifiesto_file, referencias)
                
                if coincidencias > 0:
                    st.success(f"¡Éxito! Se realizaron {coincidencias} subrayados en el manifiesto.")
                    
                    # 4. Botón de Descarga
                    st.download_button(
                        label="📥 Descargar Manifiesto Subrayado",
                        data=pdf_modificado,
                        file_name="Manifiesto_Subrayado.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.warning("No se encontraron coincidencias exactas de la factura en este manifiesto.")
                    
            except Exception as e:
                st.error(f"Ocurrió un error durante el proceso: {str(e)}")