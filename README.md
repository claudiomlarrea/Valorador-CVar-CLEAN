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

## Ejecutar local
pip install -r requirements.txt
streamlit run app.py
