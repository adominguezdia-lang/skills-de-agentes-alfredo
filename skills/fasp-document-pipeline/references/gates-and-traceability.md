# Modelo de gates de control: metadata de trazabilidad, NO firmas de identidad

## La pregunta de diseño

Cuando recibes un encargo institucional con múltiples entregables numerados (anexos, informes, productos) y un equipo de varias personas, la pregunta natural es: **¿quién firma qué?** El instinto es construir un sistema de identidad:

- Tabla de usuarios autorizados
- Validación por rol al firmar
- Autenticación, tokens, sesiones
- Registro de "quién aprobó qué" con certidumbre

**Esa es la respuesta equivocada cuando el operador del sistema es uno solo.**

## Cuándo el modelo "gates como metadata" es correcto

El modelo aplica cuando se cumplen todas estas condiciones:

- **Una persona o un equipo muy pequeño opera el sistema.** El "equipo de 14 personas" del FASP existe en el Plan de Trabajo como stakeholder externo, pero **Alfredo coordina el stack** y produce los outputs. Las otras 13 personas aparecen en la BD como referencia institucional, no como operadores.
- **El sistema de identidad agregaría fricción sin agregar valor.** Si "todos firman como Alfredo" (porque Alfredo es quien corre los scripts), validar "Alfredo tiene rol X" no agrega seguridad — solo agrega pasos.
- **El contrato es de entregables, no de workflow auditado.** El cliente quiere los 12 anexos. Quiere saber "qué falta y qué está hecho". No quiere un log de quién hizo clic en qué botón.
- **El texto del gate es trazabilidad humana, no legal.** "Avance de la matriz de congruencia" es una nota de progreso. No es un certificado de cumplimiento.

## Cuándo el modelo "gates como firmas" SÍ es correcto

El modelo alternativo (validación de identidad) es necesario cuando:

- **Múltiples personas firman con consecuencias legales o regulatorias.** Auditorías externas, certificaciones, firmas de contrato. Aquí la BD debe tener `usuarios_autorizados` con verificación de email/dominio.
- **Hay segregación de funciones obligatoria.** "Quien ejecuta el script no puede firmar el checkpoint." Esto requiere un sistema de identidad con roles.
- **El output tiene valor monetario o legal alto.** Estados financieros, informes de auditoría tributaria, reportes regulatorios.
- **El cliente pide explícitamente "que cada perfil firme con su usuario de dominio".** Esto es un requisito explícito, no una buena práctica genérica.

## El anti-patrón: sobre-ingeniería de identidad

Síntoma típico en una sesión nueva con un skill así:

1. El usuario describe el sistema y menciona "firma" o "aprobación" en algún rol.
2. El agente instintivamente propone `tabla usuarios_autorizados`, `seed inicial de los 14`, `validación contra lista`.
3. El usuario responde: **"no se ocupan esas validaciones, es innecesario, [nombre] coordina el stack completo"**.
4. El agente se da cuenta de que construyó un sistema de seguridad que nadie pidió, y que retrasa la entrega.

**La lección**: cuando escuches "firma" o "aprobación" en un sistema donde un solo operador coordina, **pregunta antes de implementar**. La respuesta por defecto es "metadata de trazabilidad", no "sistema de identidad".

## Patrón de gates de control (el modelo correcto para FASP y similares)

### Esquema de BD

```sql
CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    etapa TEXT NOT NULL,
    perfil TEXT NOT NULL,
    anexo TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('aprobado','pendiente','rechazado')),
    comentario TEXT,
    aprobador TEXT,        -- texto libre, NO validado
    fecha TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Script de registro

```python
def registrar(db, etapa, perfil, anexo, decision, aprobador="Alfredo Dominguez"):
    """Registra un gate. aprobador es texto libre."""
    # NO validación de identidad
    # NO verificación de permisos
    # Solo INSERT en la BD
    ...
```

### CLI

```bash
python3 checkpoint.py --db ./fasp.db \
    --etapa etapa_1_documental \
    --perfil coordinadora \
    --anexo "Anexo 2" \
    --decision aprobado \
    --aprobador "Alfredo Dominguez"
```

### Convención de campos

| Campo | Tipo | Significado |
|---|---|---|
| `etapa` | enum | `etapa_1_documental` / `etapa_2_campo_ars` / `etapa_3_triangulacion` |
| `perfil` | enum | `coordinadora` / `analista_senior_juridico` / `analista_senior_redes` / `analistas_junior_grafos` / `coordinacion_evaluacion` |
| `anexo` | string | Nombre del anexo: "Anexo 1", "Anexo 2", etc. |
| `decision` | enum | `aprobado` / `pendiente` / `rechazado` |
| `aprobador` | string | **Texto libre.** Convención del FASP: siempre "Alfredo Dominguez" cuando él opera. |
| `fecha` | ISO 8601 | Generada automáticamente. |

### Cómo se reporta en el dashboard

- Card global: "Gates registrados: N/15" (no "firmados", no "aprobados por")
- Tab por etapa: lista de gates con su chip (aprobado/pendiente/rechazado) + fecha + aprobador
- Lenguaje: "registro de avance" / "trazabilidad" / "control de avance"

**Nunca** "firma", "firma humana", "aprobación humana", "perfil autorizado", "autoridad sobre el producto" en el UI del dashboard.

## Cómo se invoca el LLM-2 (cuando se implemente)

Cuando LLM-2 (Constructor de matriz de congruencia) se implemente, debe:

- **Recibir como input** el campo `etapa_ciclo_fasp` que ya asignó LLM-1 (tentativo).
- **Producir como output** una lista de etapas del ciclo cuando la unidad es transversal (CSN, SESNSP, Comités de Coordinación).
- **Persistir** en una nueva columna `etapas_ciclo_fasp` (lista, no escalar) cuando el caso lo amerite.

Hasta que LLM-2 esté implementado, **el usuario revisa manualmente** las unidades cuyo texto menciona explícitamente "Consejo", "Comité", "Coordinación" o "Seguimiento" en el mismo párrafo — son candidatas a ser transversales.

## Lección operativa (para futuras sesiones)

Cuando un usuario te pida construir un sistema de "firmas" o "aprobaciones" en un skill así:

1. **Pregunta primero** si hay un solo operador o varios. Si hay uno, el modelo es gates de control (metadata).
2. **Si el usuario confirma "coordino todo" o "lo opero yo"**, no construyas sistema de identidad. Construye solo el script de registro.
3. **Si el sistema crece y aparecen múltiples operadores**, ahí sí consideras `usuarios_autorizados` + validación.
4. **Documenta en el SKILL.md del skill** que los gates son metadata, NO firmas, para que el próximo agente no caiga en el anti-patrón.
