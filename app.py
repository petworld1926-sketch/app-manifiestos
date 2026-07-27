import io
import re
import fitz  # PyMuPDF
import streamlit as st


def extraer_texto_pdf(pdf_bytes):
    """Extrae todo el texto plano de un archivo PDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texto = ""
    for page in doc:
        texto += page.get_text()
    return texto


def extraer_referencias_patron(texto):
    """Busca patrones comunes de logística (contenedores, lotes, guías) en el texto."""
    encontrados = set()

    # 1. Contenedores ISO (4 letras + 7 números, ej: MSKU1234567)
    contenedores = re.findall(r"\b[A-Z]{4}\d{7}\b", texto, re.IGNORECASE)
    encontrados.update(c.upper() for c in contenedores)

    # 2. Números largos de 6 a 12 dígitos (lotes, facturas, guías)
    numeros = re.findall(r"\b\d{6,12}\b", texto)
    encontrados.update(numeros)

    # 3. Códigos alfanuméricos con guion o dos puntos (ej: LOT-12345, REF:98765)
    alfanumericos = re.findall(
        r"\b[A-Z0-9]{2,6}[-:]\s?[A-Z0-9]{4,12}\b", texto, re.IGNORECASE
    )
    encontrados.update(a.upper() for a in alfanumericos)

    return sorted(list(encontrados))


def subrayar_manifiesto(pdf_bytes, referencias):
    """Busca las referencias extraídas dentro del manifiesto y las subraya en amarillo."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    coincidencias_totales = 0

    for page in doc:
        for ref in referencias:
            # Buscar el texto de la referencia en la página
            instancias = page.search_for(ref)
            for inst in instancias:
                annot = page.add_highlight_annot(inst)
                annot.set_colors(stroke=(1, 1, 0))  # Color amarillo
                annot.update()
                coincidencias_totales += 1

    output_buffer = io.BytesIO()
    doc.save(output_buffer)
    doc.close()
    return output_buffer.getvalue(), coincidencias_totales


# --- INTERFAZ WEB (STREAMLIT) ---
st.set_page_config(page_title="Subrayador de Manifiestos", page_icon="📝")
st.title("📝 Subrayador Automático de Manifiestos")
st.write(
    "Sube la factura para detectar automáticamente lotes, contenedores y referencias, y luego subraya sus coincidencias en el manifiesto."
)

col1, col2 = st.columns(2)
with col1:
    factura_file = st.file_uploader("1. Sube la Factura (PDF)", type=["pdf"])
with col2:
    manifiesto_file = st.file_uploader(
        "2. Sube el Manifiesto (PDF)", type=["pdf"]
    )

if factura_file and manifiesto_file:
    if st.button("🚀 Procesar y Subrayar Manifiesto"):
        with st.spinner("Procesando documentos..."):
            # 1. Extraer texto
            texto_factura = extraer_texto_pdf(factura_file.read())

            # 2. Detectar referencias por patrón
            referencias = extraer_referencias_patron(texto_factura)

            if not referencias:
                st.error(
                    "No se detectaron códigos o referencias numéricas/alfanuméricas en la factura."
                )
            else:
                st.info(
                    f"**Referencias detectadas en factura ({len(referencias)}):** "
                    + ", ".join(referencias)
                )

                # 3. Subrayar coincidencias en el manifiesto
                pdf_modificado, coincidencias = subrayar_manifiesto(
                    manifiesto_file.read(), referencias
                )

                if coincidencias > 0:
                    st.balloons()
                    st.success(
                        f"¡Éxito! Se realizaron **{coincidencias}** subrayados en el manifiesto."
                    )

                    st.download_button(
                        label="📥 Descargar Manifiesto Subrayado",
                        data=pdf_modificado,
                        file_name="Manifiesto_Subrayado.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning(
                        "Se extrajeron referencias de la factura, pero ninguna de ellas coincide exactamente con el texto dentro del manifiesto."
                    )
