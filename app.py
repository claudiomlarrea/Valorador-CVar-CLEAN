import io
import pandas as pd
import streamlit as st
from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH

from scorer import load_criteria, score_text

st.set_page_config(page_title="Valorador de CVar CLEAN - UCCuyo (TXT)", layout="wide")
st.title("Universidad Católica de Cuyo — Valorador de CVar (TXT limpio)")
st.caption("Entrada: *_CVAR_CLEAN.txt (salida del Normalizador). Exporta Excel y Word + categoría automática. (STRICT: no puntúa títulos sin finalización explícita)")

criteria = load_criteria("criteria.json")

DEBUG = st.checkbox("Debug (mostrar vista previa y coincidencias)", value=False)

uploaded = st.file_uploader("Cargar CVar limpio (.txt)", type=["txt"])
if not uploaded:
    st.info("Subí un archivo TXT limpio para iniciar la valoración.")
    st.stop()

raw = uploaded.read()
text = raw.decode("utf-8", errors="ignore")

st.success(f"Archivo cargado: {uploaded.name}")

# Vista previa (solo UI)
preview_lines = 200
lines = text.splitlines()
preview = "\n".join(lines[:preview_lines])

if DEBUG:
    with st.expander(f"Vista previa (primeras {preview_lines} líneas)"):
        st.code(preview if preview.strip() else "(archivo vacío)", language="text")

with st.spinner("Calculando puntajes con criteria.json..."):
    item_results, section_totals, total, category, categorias = score_text(text, criteria)

desc_cat = categorias.get(category, {}).get("descripcion", "")

st.markdown("---")
st.subheader("Puntaje total y categoría")
st.metric("Total acumulado", f"{total:.1f}")
st.metric("Categoría alcanzada", f"Categoría {category}")
if desc_cat:
    st.info(f"Descripción de la categoría: {desc_cat}")

# Tabla detalle por ítem
rows = []
for r in item_results:
    rows.append({
        "Sección": r.section,
        "Ítem": r.item,
        "Ocurrencias": r.count,
        "Unit points": r.unit_points,
        "Puntaje bruto": r.raw_points,
        "Tope ítem": r.item_max_points,
        "Puntaje (tope aplicado)": r.capped_item_points,
        "Evidencia (1er match)": r.evidence
    })

df_items = pd.DataFrame(rows)

st.markdown("---")
st.subheader("Detalle por sección")

for section_name, cfg in criteria.get("sections", {}).items():
    st.markdown(f"### {section_name}")
    df_sec = df_items[df_items["Sección"] == section_name].copy()
    df_sec = df_sec.sort_values(["Puntaje (tope aplicado)", "Ocurrencias"], ascending=False)

    st.dataframe(
        df_sec[["Ítem", "Ocurrencias", "Puntaje (tope aplicado)", "Tope ítem", "Evidencia (1er match)"]],
        use_container_width=True,
        hide_index=True
    )

    sec_max = cfg.get("max_points", 0)
    sec_sub = section_totals.get(section_name, 0.0)
    st.info(f"Subtotal {section_name}: {sec_sub:.1f} / máx {sec_max}")

st.markdown("---")
st.subheader("Totales por sección (tope de sección aplicado)")
df_sec_tot = pd.DataFrame([{"Sección": k, "Subtotal": v} for k, v in section_totals.items()])
df_sec_tot = df_sec_tot.sort_values("Subtotal", ascending=False)
st.dataframe(df_sec_tot, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("Exportar resultados")

# Excel
excel_out = io.BytesIO()
with pd.ExcelWriter(excel_out, engine="xlsxwriter") as writer:
    for section_name in criteria.get("sections", {}).keys():
        df_s = df_items[df_items["Sección"] == section_name].copy()
        df_s.to_excel(writer, sheet_name=section_name[:31], index=False)

    resumen = df_sec_tot.copy()
    resumen.loc[len(resumen)] = ["TOTAL", total]
    resumen.loc[len(resumen)] = ["CATEGORÍA", f"Categoría {category}"]
    resumen.to_excel(writer, sheet_name="RESUMEN", index=False)

excel_out.seek(0)

st.download_button(
    "Descargar Excel",
    data=excel_out.getvalue(),
    file_name=uploaded.name.replace(".txt", "") + "__PUNTAJE.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True
)

# Word
def export_word(df_items_local, df_sec_tot_local, total_pts, cat, cat_desc, filename):
    doc = DocxDocument()
    p = doc.add_paragraph("Universidad Católica de Cuyo — Secretaría de Investigación")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("Informe de valoración de CVar (TXT limpio) — STRICT").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("")
    doc.add_paragraph(f"Archivo evaluado: {filename}")
    doc.add_paragraph(f"Puntaje total: {total_pts:.1f}")
    doc.add_paragraph(f"Categoría alcanzada: Categoría {cat}")
    if cat_desc:
        doc.add_paragraph(cat_desc)

    doc.add_paragraph("")
    doc.add_heading("Totales por sección", level=2)
    for _, row in df_sec_tot_local.iterrows():
        doc.add_paragraph(f"- {row['Sección']}: {float(row['Subtotal']):.1f}")

    for section_name in criteria.get("sections", {}).keys():
        doc.add_heading(section_name, level=2)
        df_s = df_items_local[df_items_local["Sección"] == section_name].copy()

        cols = ["Ítem", "Ocurrencias", "Puntaje (tope aplicado)", "Tope ítem"]
        if DEBUG:
            cols.append("Evidencia (1er match)")

        if df_s.empty:
            doc.add_paragraph("Sin ítems detectados.")
        else:
            tbl = doc.add_table(rows=1, cols=len(cols))
            hdr = tbl.rows[0].cells
            for i, c in enumerate(cols):
                hdr[i].text = c

            for _, r in df_s.iterrows():
                cells = tbl.add_row().cells
                for i, c in enumerate(cols):
                    cells[i].text = str(r.get(c, ""))

        doc.add_paragraph(f"Subtotal sección: {df_sec_tot_local[df_sec_tot_local['Sección']==section_name]['Subtotal'].values[0]:.1f}" if (df_sec_tot_local['Sección']==section_name).any() else "")

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio.getvalue()

st.download_button(
    "Descargar informe Word",
    data=export_word(df_items, df_sec_tot, total, category, desc_cat, uploaded.name),
    file_name=uploaded.name.replace(".txt", "") + "__INFORME.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    use_container_width=True
)
