# Traducción al castellano de Princes of Darkness (CK3)

Este repositorio es un mod de traducción. Tu trabajo es traducir o revisar textos con las herramientas de `tools/`. **No traduzcas editando los `.yml` a mano:** usa siempre el flujo de lotes descrito abajo.

## Normas innegociables

- **Git:** no hagas `add`, `commit`, `push`, `pull`, `stash`, `reset`, `checkout` ni nada que modifique el repositorio. El usuario se encarga de git. Solo puedes usar `status`, `diff`, `log` y `show`.
- **Idioma:** castellano (España), con la terminología oficial española de Mundo de Tinieblas (glosario en `tools/glossary.tsv`). Decisiones fijas: el Hunger vampírico (la necesidad de sangre) → Ansia; wraith → wraith (Spectre, que es otra criatura, sí es Espectro); nombres propios de personajes y dinastías sin traducir, salvo los históricos con forma castellana asentada. En cambio **sí se traducen** los lemas de dinastía (`*_motto`, que son frases) y los nombres formados con nombres comunes ingleses (`Sisters of St-John` → `Hermanas de San Juan`, `Silver-Howl` → `Aullido-de-Plata`).
- **Tu trabajo termina en `spanish/`.** Nunca ejecutes `python tools/pod.py build` ni toques `mod/` (ni su `descriptor.mod`): volcar al mod y subir la versión lo hace el usuario.
- **Carpetas intocables:** `mod/` y `english/` (las actualiza el usuario).
- **Final de cada encargo:** haz siempre «el cierre» (`fix --dirty`, `verify` y `clean`) antes de dar el resumen.

## Antes de empezar

- Trabaja desde la raíz del repositorio (la carpeta que contiene este archivo). Hace falta `python` (3.8 o superior, sin dependencias) y `git`.
- **`AGENTS.md`** (este archivo) dice *qué* hacer; **`tools/TRADUCIR_LOTE.md`** dice *cómo* traducir un lote. Lee los dos antes de traducir.
- Trabaja de forma autónoma: no pidas confirmación entre lotes. Para solo en estos casos: `english/` sin commitear, errores de `pod.py` que no entiendas.

## Mapa

| Ruta | Qué es |
|---|---|
| `english/` | Inglés de la PoD de Steam Workshop (fuente) |
| `spanish/` | Traducción de trabajo. Cabecera `l_english` = archivo aún sin traducir |
| `mod/` | Mod para Steam. **No lo toques**: lo genera el usuario |
| `tools/pod.py` | Herramienta única: `python tools/pod.py -h` |
| `tools/glossary*.tsv` | Glosarios. Cada lote ya trae los términos que necesita: no hace falta abrirlos |
| `tools/local_agent.py`, `tools/menu.py` | Bucle de lotes con un modelo local (Jan) y su menú. Los lanza el usuario; tú no los necesitas |
| `tools/TRADUCIR_LOTE.md` | **Cómo traducir un lote** (reglas, marcas del juego, género). Léelo antes de traducir |
| `README.md` | Explicación completa del flujo (para personas) |
| `work_queue/` | Cola de lotes: `todo/` (por hacer), `out/` (tus respuestas), `manual/` (fallidos) |

Prefijos de lote: **U** = actualización · **B** = pendientes · **R** = revisión · **N** = nombres · **M** = textos devueltos de `manual/`.

**No decidas tú el orden ni qué contenido es más importante.** `batch` ya emite los lotes en este orden: primero lo general y compartido, luego vampiro, hombre lobo, cazadores e inquisición y, por último, el resto de líneas (wraith, fae, momias, kuei-jin, demonios…). Dentro de cada línea van antes los textos de interfaz y los cortos que se ven siempre, y los eventos largos al final. Se configura en `splat_priority` y `priority` de `tools/config.json`; si el usuario quiere otro orden, lo cambia ahí. Tradúcelos tal como salgan.

## Qué hacer según el encargo

Ejecuta los comandos desde la raíz del repositorio. En cada receta, «el bucle» es el de `tools/TRADUCIR_LOTE.md` con el prefijo indicado (`python tools/pod.py next --prefix X`). Repítelo hasta `NO QUEDAN LOTES` o hasta el límite que te hayan dado. Toda receta termina con **el cierre**, descrito más abajo.

### «Traduce lo nuevo de la actualización»
También se pedirá como «los nuevos archivos», «lo nuevo», «la actualización», «la nueva versión» o «los cambios del mod». En todos los casos se traducen los archivos nuevos **y** las claves nuevas o cambiadas en archivos ya existentes.
1. `git status -- english/`: si hay cambios sin commitear, **para** y pide al usuario que haga commit. Si git no está disponible, avísale y no sigas.
2. `python tools/pod.py sync --dry-run` → si no hay cambios y ya existen lotes `U` en la cola, salta al paso 5.
3. `python tools/pod.py sync`
4. `python tools/pod.py batch --scope update`
5. El bucle con prefijo **U**. Terminas cuando no quedan lotes U.

### «Traduce pendientes» (opcional: de un archivo o carpeta concretos)
1. `python tools/pod.py status`
2. `python tools/pod.py batch [--limit N]`. Usa `--files "<patrón>"` solo si el usuario nombra una zona concreta; si no, deja que `batch` siga el orden de prioridad.
3. El bucle con prefijo **B**.

### «Revisa / mejora lo traducido» (opcional: una regla o unos archivos)
1. Solo si te lo piden: `python tools/pod.py fix --dry-run` y después `fix`.
2. `python tools/pod.py check [--rule R] [--files …]`, con R = `tokens`, `custom`, `spaces`, `punct`, `glossary`, `display` o `english`.
3. `python tools/pod.py batch --mode review --rule R [--files …] [--limit N]`
4. El bucle con prefijo **R**. Devuelve solo las líneas que cambies: lo que dejes igual se anota como revisado y no se te volverá a proponer mientras ese texto no cambie.

### «Adapta los nombres de personajes y dinastías»
1. `python tools/pod.py batch --mode names`
2. El bucle con prefijo **N** (sección «Modo NOMBRES» de `tools/TRADUCIR_LOTE.md`).

### «Traduce lo que quedó en manual/»
Son los textos que no pasaron la validación dos veces.
1. `python tools/pod.py clean --requeue` → vuelven a la cola como lotes **M**, aparte del resto.
2. El bucle con prefijo **M**. Cada lote trae en `MOTIVO:` por qué se rechazó: corrige exactamente eso.

### «Sigue con lo que haya» / sin más contexto
`python tools/pod.py next` y el bucle con el prefijo del lote que salga.

## El cierre (siempre, al acabar los lotes)

1. `python tools/pod.py fix --dirty` → arreglos mecánicos (dobles espacios, `GetCustom('ES_O')`, `Concept (`, `| E]`, comillas sin cerrar) solo en los archivos que has tocado.
2. `python tools/pod.py verify --batch --limit 10` → revisa **solo las claves que has escrito** y, si hay avisos, crea como mucho 10 lotes **R** con ellas (el resto saldrá en la siguiente verificación; las claves que ya han dado 3 vueltas de revisión se aparcan solas en `tools/reviewed.tsv`).
3. Si ha creado lotes R, pasa **esos lotes concretos** una vez con el bucle (no la cola entera: puede arrastrar lotes R de otras sesiones) y vuelve a `verify`. Si el segundo intento deja los mismos avisos, no insistas: anótalos en el resumen.
4. `python tools/pod.py clean` → quita de la cola lo ya resuelto y lo caducado; nunca toca lotes pendientes ni el historial de `done/`.
5. `python tools/pod.py status`.
6. Resumen para el usuario: qué has traducido, qué ha arreglado `fix`, qué avisos quedan y qué hay en `work_queue/manual/`. Recuérdale que `build`, la versión y git son cosa suya.

## Trabajo en paralelo

Varias sesiones pueden trabajar a la vez si cada una usa un prefijo distinto (p. ej. una con **B** y otra con **M**): `pod.py` bloquea la cola mientras escribe, así que no se pisan. Con el mismo prefijo, en cambio, las dos cogerían el mismo lote y una de ellas traduciría para nada. En ese caso, el cierre se hace una sola vez, cuando hayan terminado todas. Lo que acabe en `work_queue/manual/` (JSON con el texto, el motivo del rechazo y el intento fallido) no se reintenta solo: resúmelo para el usuario.
