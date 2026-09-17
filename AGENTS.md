# Traducción al castellano de Princes of Darkness (CK3)

Este repositorio es un mod de traducción. Tu trabajo es traducir o revisar textos con las herramientas de `tools/`. **No traduzcas editando los `.yml` a mano:** usa siempre el flujo de lotes descrito abajo.

## Normas innegociables

- **Git:** no hagas `add`, `commit`, `push`, `pull`, `stash`, `reset`, `checkout` ni nada que modifique el repositorio. El usuario se encarga de git. Solo puedes usar `status`, `diff`, `log` y `show`.
- **Idioma:** castellano (España), con la terminología oficial española de Mundo de Tinieblas (glosario en `tools/glossary.tsv`). Decisiones fijas: Hunger → Ansia; wraith → wraith; las dinastías no se traducen excepto casos especiales (nombres históricos, por ejemplo).
- **Tu trabajo termina en `working/spanish/`.** Nunca ejecutes `python tools/pod.py build` ni toques `spanish_translation/` (ni su `descriptor.mod`): volcar al mod y subir la versión lo hace el usuario.
- **Carpetas intocables:** `spanish_translation/`, `simp_chinese/` (ignórala: está desactualizada), `original_text/` (la actualiza el usuario).
- **Final de cada encargo:** haz siempre «el cierre» (`fix --dirty` + `verify`) antes de dar el resumen.

## Antes de empezar

- Trabaja desde la raíz del repositorio (la carpeta que contiene este archivo). Hace falta `python` (3.8 o superior, sin dependencias) y `git`.
- **`AGENTS.md`** (este archivo) dice *qué* hacer; **`tools/TRADUCIR_LOTE.md`** dice *cómo* traducir un lote. Lee los dos antes de traducir.
- Trabaja de forma autónoma: no pidas confirmación entre lotes. Para solo en estos casos: `original_text` sin commitear, errores de `pod.py` que no entiendas.

## Mapa

| Ruta | Qué es |
|---|---|
| `original_text/english/` | Inglés de la PoD de Steam Workshop (fuente) |
| `working/spanish/` | Traducción de trabajo. Cabecera `l_english` = archivo aún sin traducir |
| `spanish_translation/` | Mod para Steam. **No lo toques**: lo genera el usuario |
| `tools/pod.py` | Herramienta única: `python tools/pod.py -h` |
| `tools/TRADUCIR_LOTE.md` | **Cómo traducir un lote** (reglas, marcas del juego, género). Léelo antes de traducir |
| `README.md` | Explicación completa del flujo (para personas) |
| `work_queue/` | Cola de lotes: `todo/` (por hacer), `out/` (tus respuestas), `manual/` (fallidos) |

Prefijos de lote: **U** = actualización · **B** = pendientes · **R** = revisión · **N** = nombres.

**No decidas tú el orden ni qué contenido es más importante.** `batch` ya emite los lotes en el orden acordado: primero lo general y compartido, luego vampiro, hombre lobo, cazadores e inquisición y, por último, el resto de líneas (wraith, fae, momias, kuei-jin, demonios…). Dentro de cada línea van antes los textos de interfaz y los cortos que se ven siempre, y los eventos largos al final. Se configura en `splat_priority` y `priority` de `tools/config.json`; si el usuario quiere otro orden, lo cambia ahí. Tradúcelos tal como salgan.

## Qué hacer según el encargo

Ejecuta los comandos desde la raíz del repositorio. En cada receta, «el bucle» es el de `tools/TRADUCIR_LOTE.md` con el prefijo indicado (`python tools/pod.py next --prefix X`). Repítelo hasta `NO QUEDAN LOTES` o hasta el límite que te hayan dado. Toda receta termina con **el cierre**, descrito más abajo.

### «Traduce lo nuevo de la actualización»
También se pedirá como «los nuevos archivos», «lo nuevo», «la actualización», «la nueva versión» o «los cambios del mod». En todos los casos se traducen los archivos nuevos **y** las claves nuevas o cambiadas en archivos ya existentes.
1. `git status -- original_text`: si hay cambios sin commitear, **para** y pide al usuario que haga commit. Si git no está disponible, avísale y no sigas.
2. `python tools/pod.py sync --dry-run` → si no hay cambios y ya existen lotes `U` en la cola, salta al paso 5.
3. `python tools/pod.py sync`
4. `python tools/pod.py batch --scope update`
5. El bucle con prefijo **U**. Terminas cuando no quedan lotes U.

### «Traduce pendientes» (opcional: de un archivo o carpeta concretos)
1. `python tools/pod.py status`
2. `python tools/pod.py batch [--files "traits/*"] [--limit N]`
3. El bucle con prefijo **B**.

### «Revisa / mejora lo traducido» (opcional: una regla o unos archivos)
1. Solo si te lo piden: `python tools/pod.py fix --dry-run` y después `fix`.
2. `python tools/pod.py check [--rule R] [--files …]`, con R = `tokens`, `custom`, `spaces`, `punct`, `glossary`, `display` o `english`.
3. `python tools/pod.py batch --mode review --rule R [--files …] [--limit N]`
4. El bucle con prefijo **R**. Devuelve solo las líneas que cambies.

### «Adapta los nombres de personajes»
1. `python tools/pod.py batch --mode names`
2. El bucle con prefijo **N** (sección «Modo NOMBRES» de `tools/TRADUCIR_LOTE.md`).

### «Sigue con lo que haya» / sin más contexto
`python tools/pod.py next` y el bucle con el prefijo del lote que salga.

## El cierre (siempre, al acabar los lotes)

1. `python tools/pod.py fix --dirty` → arreglos mecánicos (dobles espacios, `GetCustom('ES_O')`, `Concept (`, `| E]`, comillas sin cerrar) solo en los archivos que has tocado.
2. `python tools/pod.py verify --batch` → revisa **solo las claves que has escrito** y, si hay avisos, crea lotes **R** con ellas.
3. Si ha creado lotes R, pásalos una vez con el bucle (prefijo **R**) y vuelve a `verify`. Si el segundo intento deja los mismos avisos, no insistas: anótalos en el resumen.
4. `python tools/pod.py status`.
5. Resumen para el usuario: qué has traducido, qué ha arreglado `fix`, qué avisos quedan y qué hay en `work_queue/manual/`. Recuérdale que `build`, la versión y git son cosa suya.

## Si eres un modelo orquestador

Puedes preparar los lotes (pasos de `sync`, `batch` y `check`) y repartir el bucle entre subagentes baratos, asignando rangos concretos de lotes (p. ej. `U0001`–`U0010`). `apply` bloquea la cola, así que pueden trabajar en paralelo. Lo que acabe en `work_queue/manual/` resuélvelo tú editando y aplicando un lote de reintento, o déjalo anotado para el usuario.
