# Prompt de conversión PDF→Markdown — v3 (OCR / escaneos)

## Cuándo usar

Cuando el PDF es escaneado (sin texto embebido) y se ha recurrido a OCR. El texto crudo contiene ruido típico de OCR: caracteres mal reconocidos, líneas pegadas, espacios irregulares.

## Cambios respecto a v1

- Tolerante a errores OCR comunes.
- Acepta texto "sucio" y produce MD razonable.
- Marca con `[¿ilegible?]` lo que no se puede reconstruir.

## Plantilla

```
Eres un conversor de texto OCR a Markdown. El texto tiene errores de reconocimiento.

Texto OCR:
---
{raw_text}
---

Reglas:
1. Headings cuando el patrón sea claro (línea corta aislada, mayúsculas).
2. Listas con - o números.
3. Si una palabra es claramente errónea (ej. "Sccretaría" → "Secretaría"), corrige solo si es muy evidente. Si no, marca con [¿ilegible?].
4. NO omitas contenido reconocible.
5. NO inventes secciones.

Markdown resultante:
```