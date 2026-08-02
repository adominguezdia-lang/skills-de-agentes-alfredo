# Setup de AWS Bedrock para ejecutar el skill FASP

Receta operativa probada con el usuario (Alfredo Domínguez) en julio 2026.

## TL;DR

```bash
# 1. Crear perfil Hermes dedicado
hermes profile create fasp-bedrock

# 2. Configurar provider y modelo
hermes -p fasp-bedrock config set model.provider bedrock
hermes -p fasp-bedrock config set model.default us.anthropic.claude-sonnet-4-5-20250929-v1:0

# 3. Smoke test
fasp-bedrock chat -q "Di OK y nada mas" --tools ''
# → debe devolver "OK" en ~7s

# 4. Instalar skills en el perfil
mkdir -p ~/.hermes/profiles/fasp-bedrock/skills/productivity
cp -r ~/.hermes/skills/productivity/fasp-document-pipeline ~/.hermes/profiles/fasp-bedrock/skills/productivity/
cp -r ~/.hermes/skills/productivity/pdf-to-knowledge-graph ~/.hermes/profiles/fasp-bedrock/skills/productivity/

# 5. Uso
fasp-bedrock chat -q "Procesa /tmp/norma.pdf con el skill FASP" --tools 'terminal,file'
```

## Credenciales AWS (sin instalar `aws` CLI)

El usuario tiene `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_REGION` ya configuradas en el entorno. NO se necesita instalar `aws` CLI. El SDK de Python (`boto3`) las usa directamente.

Verificación rápida con `boto3`:

```python
import boto3
from botocore.config import Config
cfg = Config(read_timeout=10, retries={'max_attempts': 1, 'mode': 'standard'})
sts = boto3.client('sts', config=cfg)
print(sts.get_caller_identity())
# → Account, Arn (verificar que NO sea root), UserId
```

## Modelos disponibles (julio 2026)

Probados con cuenta `arn:aws:iam::829911537909:user/adominguez`:

| Model ID | Estado | Costo aprox. | Uso recomendado |
|---|---|---|---|
| `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | ✅ Accesible | $$$ | Producción, revisión de calidad |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | ✅ Accesible | $ | Batch, clasificación contra taxonomía cerrada |

Otros candidatos probados y NO accesibles:
- `us.anthropic.claude-sonnet-4-20250514-v1:0` → ResourceNotFoundException
- `us.anthropic.claude-3-5-sonnet-20241022-v2:0` → ResourceNotFoundException
- `us.anthropic.claude-3-5-haiku-20241022-v1:0` → ResourceNotFoundException

## Latencia esperada por operación

| Operación | CLI directo | Agente Bedrock (Sonnet) | Agente Bedrock (Haiku) |
|---|---|---|---|
| PDF → MD (50 KB, 3 páginas) | < 1s | ~10-15s (1 tool call) | ~5-8s |
| LLM-1 sobre el MD | < 0.5s | ~8-12s (1 tool call) | ~4-6s |
| PY-1 + Anexo 1 | < 0.5s | ~8-12s | ~4-6s |
| Checkpoint | < 0.1s | ~6-10s | ~3-5s |
| **Pipeline completo (6 pasos)** | **~25-30s** | **>180s (timeout del shell)** | **~80-120s** |

**Implicación práctica**: NO pidas al agente Bedrock que ejecute el pipeline completo de muchos pasos. Usa el agente para revisión/supervisión, y los scripts CLI directos para batch.

## Pitfalls conocidos

1. **Perfil sin `.env` poblado**. `hermes profile create` deja un `.env` casi vacío. Funciona desde shell normal (hereda env), pero NO desde el TUI gateway (carga el `.env` propio). Solución: `cp ~/.hermes/.env ~/.hermes/profiles/fasp-bedrock/.env` o poblar las AWS_* manualmente. **Para este caso no hizo falta** porque las credenciales ya estaban en el shell env del usuario y todos los `fasp-bedrock chat -q` los heredaron correctamente.

2. **`fasp-bedrock -q "..."` no funciona**. El wrapper es `hermes -p fasp-bedrock "$@"`. El `-q` vive en el subcomando `chat`: `fasp-bedrock chat -q "..."`. Sin `chat`, el comando falla con "argument command: invalid choice".

3. **Timeout del shell a 180s**. Cuando el agente Bedrock ejecuta varios tool calls consecutivos, cada uno incurre en latencia HTTP (~5-15s) y se acumula. Para pipelines largos, ejecuta los scripts directamente desde el shell, no a través del agente.

4. **El perfil NO comparte skills con el perfil principal**. Cada perfil tiene su propio árbol `~/.hermes/profiles/<name>/skills/`. Tienes que copiar explícitamente los skills que necesites al perfil. Para evitar esto, edita `config.yaml` del perfil y usa `skills_paths` adicionales.