# Skills de Agentes Alfredo

Catálogo de skills personalizados para agentes IA, creados y mantenidos por Alfredo Domínguez. Cada skill es autocontenido, distribuible y sigue las convenciones del framework Hermes Agent.

## Skills disponibles

| Skill | Descripción | Categoría |
|---|---|---|
| [`biblio-metadata-extractor`](skills/biblio-metadata-extractor/) | Extrae metadatos bibliográficos (PDFs, páginas web, informes institucionales, libros, artículos académicos) a un JSON estricto de 12 claves. | `productivity` |

## Estructura del repositorio

```
skills-de-agentes-alfredo/
├── README.md                          # este archivo (catálogo)
└── skills/
    └── <nombre-del-skill>/            # un directorio por skill
        ├── SKILL.md                   # definición del skill (frontmatter + reglas)
        ├── README.md                  # guía rápida de instalación/uso
        ├── references/                # schemas, reglas extendidas, materiales de apoyo
        ├── templates/                 # plantillas listas para rellenar
        ├── examples/                  # ejemplos trabajados
        └── scripts/                   # utilidades (validadores, helpers)
```

## Convención de nombrado

Cada skill vive en su propio directorio bajo `skills/` con el nombre en kebab-case (ej. `biblio-metadata-extractor`). La carpeta incluye siempre:

- `SKILL.md` con frontmatter YAML (`name`, `description`, `version`, `author`, `license`, `metadata.hermes.tags`).
- `README.md` con instrucciones de instalación y uso.
- Al menos un ejemplo trabajao en `examples/`.
- Recursos de soporte en `references/`, `templates/` o `scripts/` según convenga.

## Cómo añadir un nuevo skill

1. Crear la carpeta `skills/<nombre-del-skill>/` siguiendo la estructura anterior.
2. Asegurarse de que `SKILL.md` valida con el loader de Hermes Agent (frontmatter ≤ 1024 chars de descripción, ≤ 100 000 chars totales).
3. Incluir al menos un ejemplo real que pase cualquier validador incluido en `scripts/`.
4. Actualizar la tabla de skills disponibles en este README.
5. Hacer commit con mensaje `add(skill): <nombre-del-skill>`.

## Licencia

MIT. Cada skill individual puede tener su propia licencia especificada en su `SKILL.md` (por defecto MIT).

## Contacto

Repositorio mantenido por Alfredo Domínguez · [adominguezdia-lang](https://github.com/adominguezdia-lang)