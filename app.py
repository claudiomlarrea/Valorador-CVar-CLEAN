import io
import pandas as pd
import streamlit as st
from docx import Document

from scorer import load_criteria, score_text

st.set_page_config(page_title="Valorador CVar CLEAN (TXT)", layout="wide")
st.title("Valorador de CVar CLEAN (Repo 2)")
st.caption("Entrada: *_CVAR_CLEAN.txt (salida del Normalizador). Salidas: Excel + Word con puntaje y categoría.")

# Carga criterios
try:
    criteria = load_criteria("criteria.json")
except Exception as e:
    st.error(f"No se pudo leer criteria.json: {e}")
    st.stop()

uploaded = st.file_uploader("Subí el archivo TXT limpio (CVAR_CLEAN)", type=["txt"])

if uploaded is None:
    st.info("Esperando archivo TXT limpio...")
    st.stop()

text = uploaded.read().decode("utf-8", errors="ignore")

with st.spinner("Calculando puntajes..."):
    results, section_totals, total, category = score_text(text, criteria)

# DataFrame
rows = []
for r in results:
    rows.append({
        "Sección": r.section,
        "Ítem": r.item,
        "Conteo": r.count,
        "Puntos unitarios": r.unit_points,
        "Puntos (bruto)": r.raw_points,
        "Tope ítem": r.max_points,
        "Puntos (tope aplicado)": r.capped_points,
        "Evidencia (primer match)": r.evidence
    })
df = pd.DataFrame(rows)

st.success(f"Puntaje total: {total:.1f} — Categoría: {category}")
c1, c2 = st.columns([2, 1])
with c1:
    st.dataframe(df, use_container_width=True, hide_index=True)
with c2:
    st.subheader("Totales por sección")
    st.write(pd.DataFrame([section_totals]).T.rename(columns={0: "Puntos"}))

# Excel (en memoria)
excel_buf = io.BytesIO()
with pd.ExcelWriter(excel_buf, engine="xlsxwriter") as writer:
    df.to_excel(writer, sheet_name="Detalle", index=False)
    pd.DataFrame([section_totals]).T.reset_index().rename(columns={"index": "Sección", 0: "Puntos"}).to_excel(writer, sheet_name="Secciones", index=False)
    pd.DataFrame([{"Puntaje total": total, "Categoría": category}]).to_excel(writer, sheet_name="Resumen", index=False)
excel_buf.seek(0)

# Word (en memoria)
doc = Document()
doc.add_heading("Informe de valoración — CVar (TXT limpio)", level=1)
doc.add_paragraph(f"Archivo evaluado: {uploaded.name}")
doc.add_paragraph(f"Puntaje total: {total:.1f}")
doc.add_paragraph(f"Categoría: {category}")

doc.add_heading("Totales por sección", level=2)
for sec, pts in section_totals.items():
    doc.add_paragraph(f"- {sec}: {pts:.1f}")

doc.add_heading("Detalle por ítem (con evidencia)", level=2)
for _, row in df.iterrows():
    if int(row["Conteo"]) > 0:
        doc.add_paragraph(f'• {row["Sección"]} — {row["Ítem"]}: {row["Puntos (tope aplicado)"]:.1f} pts (conteo={row["Conteo"]})')
        if row["Evidencia (primer match)"]:
            doc.add_paragraph(f'Evidencia: {row["Evidencia (primer match)"]}')

word_buf = io.BytesIO()
doc.save(word_buf)
word_buf.seek(0)

st.download_button(
    "⬇️ Descargar Excel (puntajes)",
    data=excel_buf,
    file_name=uploaded.name.replace(".txt", "") + "__PUNTAJE.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

st.download_button(
    "⬇️ Descargar Word (informe)",
    data=word_buf,
    file_name=uploaded.name.replace(".txt", "") + "__INFORME.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    use_container_width=True
)
