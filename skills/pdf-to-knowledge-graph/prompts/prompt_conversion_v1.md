# Prompt de conversión PDF→Markdown — v1 (base)

## Objetivo

Convertir texto crudo extraído de un PDF en Markdown limpio, preservando:
- Estructura jerárquica (headings).
- Listas (ordenadas y no ordenadas).
- Énfasis (negritas, cursivas) si están en el original.
- Saltos de párrafo.

## Reglas de integridad

1. **No omitir contenido**. Todo párrafo del original debe aparecer en el MD.
2. **No resumir**. La conversión es literal, no parafraseada.
3. **No inventar headings**. Solo `#`, `##`, etc. cuando el original tiene estructura jerárquica visible.
4. **Preservar el orden** del original.

## Plantilla de prompt

```
Eres un conversor de texto crudo de PDF a Markdown.

Texto crudo:
---
{raw_text}
---

Convierte a Markdown siguiendo estas reglas:
1. Usa # para el título principal, ## para secciones, ### para subsecciones.
2. Convierte listas con guiones o números en listas Markdown.
3. NO omitas párrafos.
4. NO resumas.
5. NO agregues contenido que no esté en el original.
6. Si una sección no tiene heading claro, déjala como párrafo.

Markdown resultante:
```