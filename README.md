# Valorador-CVarCLEAN-TXT-Strict (UCCuyo)

App Streamlit para valorar archivos *_CVAR_CLEAN.txt generados por el Normalizador.

## Criterio STRICT (clave)
- Doctorado / Maestría / Especialización / Grado / Profesorado / Posdoc:
  SOLO puntúa si hay evidencia explícita de finalización:
  - "Año de finalización: YYYY" (o MM/YYYY)
  - "Situación del nivel: Completo"
  - cues: "finalizado/egresado/graduado/título obtenido/título otorgado"
- Si aparece "Actualidad / En curso / Cursando" → NO puntúa.
- Los títulos NO se cuentan fuera de la sección "FORMACIÓN ACADÉMICA" (bloqueo anti-falsos positivos).

## Flujo
1. Normalizar el PDF en **Normalizador-de-CVar** → descargar `*_CVAR_CLEAN.txt`
2. Subir ese `.txt` en esta app (no el PDF)

## Ejecutar local
```bash
pip install -r requirements.txt
python3 -m streamlit run app.py
```
→ http://localhost:8501
