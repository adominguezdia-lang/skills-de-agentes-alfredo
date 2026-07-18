# Prompt de conversión PDF→Markdown — v2 (con manejo de tablas)

## Cambios respecto a v1

- Añade reconocimiento y conversión de tablas a formato GFM (pipe tables).
- Mejor manejo de bloques multi-columna.

## Plantilla

```
Eres un conversor de texto crudo de PDF a Markdown con énfasis en tablas.

Texto crudo:
---
{raw_text}
---

Reglas:
1. Headings: # para título principal, ## secciones, ### subsecciones.
2. Listas con guillas o números → listas Markdown.
3. TABLAS: detecta filas y columnas; conviértelas a sintaxis GFM:
   | col1 | col2 |
   |------|------|
   | dato | dato |
4. NO omitas contenido, NO resumas, NO inventes.
5. Si una columna está implícita (ej. "De la Subsecretaría: ..."), usa blockquote >.

Markdown resultante:
```