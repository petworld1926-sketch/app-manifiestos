import io
import re
import zipfile
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


def subrayar_manifiestos_lote(manifiestos_files, referencias):
    """Subraya las referencias en los manifiestos, asegurando que cada referencia

    solo se subraye una única vez globalmente.
    """
    referencias_ya_subrayadas = set()
    manifiestos_procesados = {}  # {nombre_archivo: pdf_bytes}
    total_coincidencias = 0

    for m_file in manifiestos_files:
        pdf_bytes = m_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        coincidencias_en_este_doc = 0

        for page in doc:
            for ref in referencias:
                # Si la referencia ya se subrayó previamente en algún documento/página, se omite
                if ref in referencias_ya_subrayadas:
                    continue

                instancias = page.search_for(ref)
                if instancias:
                    # Subrayar solo la PRIMERA aparición de esta referencia
                    inst = instancias[0]
                    annot = page.add_highlight_annot(inst)
                    annot.set_colors(stroke=(1, 1, 0))  # Color amarillo
                    annot.update()

                    # Marcar la referencia como ya subrayada
                    referencias_ya_subrayadas.add(ref)
                    coincidencias_en_este_doc += 1
                    total_coincidencias += 1

        output_buffer = io.BytesIO()
        doc.save(output_buffer)
        doc.close()

        manifiestos_procesados[m_file.name] = output_buffer.getvalue()

    return (
        manifiestos_procesados,
        total_coincidencias,
        list(referencias_ya_subrayadas),
    )


# --- INTERFAZ WEB (STREAMLIT) ---
st.set_page_config(
    page_title="Subrayador Múltiple de Manifiestos", page_icon="📝"
)
st.title("📝 Subrayador Masivo de Manifiestos")
st.write(
    "Sube la factura y selecciona todos tus manifiestos al mismo tiempo. Las referencias solo se subrayarán **una sola vez**."
)

col1, col2 = st.columns(2)
with col1:
    factura_file = st.file_uploader("1. Sube la Factura (PDF)", type=["pdf"])
with col2:
    manifiestos_files = st.file_uploader(
        "2. Sube los Manifiestos (Puedes elegir varios PDF)",
        type=["pdf"],
        accept_multiple_files=True,
    )

if factura_file and manifiestos_files:
    if st.button("🚀 Procesar todos los Manifiestos"):
        with st.spinner(
            f"Procesando {len(manifiestos_files)} manifiesto(s)..."
        ):
            # 1. Extraer texto de la factura
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

                # 3. Subrayar en lote (solo una vez por referencia)
                resultados, total_subrayados, refs_subrayadas = (
                    subrayar_manifiestos_lote(manifiestos_files, referencias)
                )

                if total_subrayados > 0:
                    st.balloons()
                    st.success(
                        f"¡Éxito! Se subrayaron **{total_subrayados}** referencias únicas en total."
                    )

                    # Crear un archivo ZIP con todos los PDFs modificados
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(
                        zip_buffer, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
                        for nombre, pdf_data in resultados.items():
                            zip_file.writestr(
                                f"Subrayado_{nombre}", pdf_data
                            )

                    st.download_button(
                        label="📥 Descargar todos los Manifiestos (.ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="Manifiestos_Subrayados.zip",
                        mime="application/zip",
                    )
                else:
                    st.warning(
                        "Se encontraron referencias en la factura, pero ninguna coincidió con el texto de los manifiestos subidos."
                    )
