# Princes of Darkness · Traducción al castellano

Mod de traducción al castellano (España) de *Princes of Darkness* para Crusader Kings III ([Steam Workshop 3303353422](https://steamcommunity.com/sharedfiles/filedetails/?id=3303353422)).

Versión de [Princes of Darkness](https://steamcommunity.com/workshop/filedetails/?id=2216659254) para la que está hecha: <!-- base-version -->1.19.0.6 «Descent of the Dragons»<!-- /base-version -->.

> **Para agentes e IA:** el punto de partida es **[AGENTS.md](AGENTS.md)** (qué hacer según el encargo) y, para traducir, **[tools/TRADUCIR_LOTE.md](tools/TRADUCIR_LOTE.md)**. El trabajo de un agente termina en `spanish/`: nada de editar `.yml` a mano, ejecutar `build`, tocar `mod/` ni modificar el repositorio con git.

## Documentación

| Archivo | Para quién | Contenido |
|---|---|---|
| `README.md` | Personas | Este documento: el flujo completo y la guía de uso |
| `AGENTS.md` (y `CLAUDE.md`, que lo importa) | Agentes | **Qué** hacer: normas y una receta por encargo |
| `tools/TRADUCIR_LOTE.md` | Agente traductor | **Cómo** traducir un lote: bucle, idioma, marcas del juego, género, nombres |

## Cómo funciona

Los scripts hacen todo lo mecánico y el modelo de IA solo traduce textos sueltos. Un script valida cada respuesta antes de escribirla, así que un error del modelo nunca rompe un archivo.

```
english/ ──sync──► spanish/ ──batch──► work_queue/todo/U0001.txt
                      ▲                          │  (agente: tools/TRADUCIR_LOTE.md)
                      └──── apply (valida) ◄──── work_queue/out/U0001.txt
spanish/ ──build──► mod/  (se sube a Steam)
```

- **Marca de «sin traducir»:** un archivo de `spanish/` con nombre `_l_spanish.yml` y cabecera `l_english` está pendiente. `apply` cambia la cabecera a `l_spanish:` cuando el archivo queda completo.
- **Prefijos de lote:** **U** = actualización · **B** = pendientes · **R** = revisión · **N** = nombres · **M** = textos devueltos de `manual/`.
- **Ahorro:** cada lote lleva solo las entradas del glosario que aparecen en sus textos; los textos repetidos se traducen una vez, y lo que ya está traducido en otra clave con el mismo texto se rellena sin IA (memoria de traducción).
- **Rechazos:** lo que no pasa la validación vuelve en un lote de reintento con el motivo; si falla dos veces, va a `work_queue/manual/`.

| Carpeta o pieza | Qué es |
|---|---|
| `english/` | Inglés de la PoD de Steam Workshop: la fuente |
| `spanish/` | Traducción de trabajo |
| `mod/` | Mod listo para Steam (descriptor y `localization/spanish`); lo genera `build` |
| `tools/pod.py` | Script único (solo biblioteca estándar). `python tools/pod.py -h` |
| `tools/config.json` | Rutas, tamaño de lote, orden de prioridad, archivos que no se traducen, último commit sincronizado |
| `tools/glossary.tsv` | Glosario del proyecto: manda sobre los demás. Se edita a mano |
| `tools/glossary_mod.tsv` | Generado con `pod.py glossary` a partir de los conceptos ya traducidos del mod |
| `tools/glossary_books.tsv` | Generado con `tools/extract_glossaries.py` desde los glosarios oficiales en PDF de la raíz |
| `tools/keep_english.txt` | Claves que se quedan en inglés; `apply` lo amplía solo |
| `work_queue/` | Cola de lotes y registros de trabajo (no se versiona) |

**Los tres glosarios**, de menor a mayor prioridad: los libros, los conceptos del mod y el del proyecto. Solo las entradas de `glossary.tsv` marcadas con `l` se comprueban con `check --rule glossary`; las de los libros son orientativas y llegan al agente en la cabecera de cada lote.

Para regenerar el de los libros, tras añadir o cambiar un PDF (necesita `pdftotext`):

```bash
python tools/extract_glossaries.py
```

Se queda solo con los términos que aparecen en `english/`, descarta las palabras corrientes (frecuentes en la localización inglesa del CK3) y no repite lo que ya está en los otros dos.

## Modo 1 · Actualización de PoD

1. **(Usuario)** Copia el inglés de la PoD de Workshop a `english/` y hace commit.
2. `python tools/pod.py sync --dry-run` → muestra qué va a cambiar.
3. `python tools/pod.py sync`:
   - Archivos nuevos: se copian a `spanish/` renombrados y con cabecera `l_english`.
   - Claves nuevas: se insertan en su sitio, en inglés.
   - Claves cuyo inglés ha cambiado: se ponen en inglés y la traducción antigua se guarda para que el agente la reutilice.
   - Claves borradas en origen: se eliminan. Las que solo existen en español se dejan y se avisa.
   - Con `--prune`, los archivos que ya no existen en inglés se mueven a `work_queue/removed/`.
4. `python tools/pod.py batch --scope update` → lotes **U** solo con lo que trajo el `sync`.
5. El agente traduce los lotes y cierra con `fix --dirty`, `verify --batch` y `clean` (ver «El cierre» en `AGENTS.md`).
6. **(Usuario)** Revisa el diff de `spanish/`, ejecuta `build` con la versión nueva y hace commit.

## Modo 2 · Pendientes

`python tools/pod.py status` → `python tools/pod.py batch [--limit N]` → agente → `build` (usuario).

**Orden de prioridad.** `batch` emite los lotes ordenados sin que el agente tenga que decidir nada:

1. **Línea de juego** (`splat_priority` en `config.json`): general y compartido → vampiro → hombre lobo → cazadores e inquisición → otras líneas (wraith, fae, momias, kuei-jin, demonios…). Se deduce del nombre del archivo; lo que no encaja en ninguna cuenta como general, que es la mayor parte porque el vampiro es la línea por defecto del mod.
2. **Tipo de archivo** (`priority`): conceptos → rasgos → interfaz → interacciones → decisiones → … y los eventos largos al final.

`--files "<carpeta>/*"` fuerza una zona concreta y se salta ese orden.

**Nombres de personajes y dinastías.** Quedan fuera de los lotes normales. `batch --mode names` los prepara en lotes **N** de 200, y el agente devuelve solo los que tienen forma castellana asentada (Helena de Troya, Menelao, Comneno…); el resto se queda igual.

## Modo 3 · Mejoras

1. `python tools/pod.py fix --dry-run` y después `fix`: arreglos seguros sin IA (dobles espacios, `GetCustom('ES_O')`, `Concept (`, `| E]`, comillas sin cerrar). `--dirty` lo limita a los archivos modificados y `--files` a un patrón.
2. `python tools/pod.py check [--rule R] [--files …]` → informe de defectos. Reglas:
   - `tokens`: marcas del juego perdidas o cambiadas (la más importante).
   - `custom`: funciones de género inexistentes.
   - `spaces`: espacios sobrantes.
   - `punct`: faltan ¿ o ¡, o sobran («¡» añadido por confundir el cierre `#!` con una exclamación).
   - `glossary`: término del glosario no respetado (solo entradas marcadas con `l`).
   - `display`: texto de `Glossary(...)` o `Concept(...)` sin traducir.
   - `english`: palabras inglesas sueltas.
3. `python tools/pod.py batch --mode review --rule R` → lotes **R**; el agente devuelve solo las líneas que corrige → `build` (usuario).

`check` mira archivos completos, defectos antiguos incluidos. `verify` mira solo las claves escritas por los lotes aplicados (desde la última verificación, o todas con `--all`): sirve para auditar el trabajo de un agente sin mezclarlo con lo anterior.

Los cambios terminológicos globales (p. ej. Hambre → Ansia) se deciden antes y se añaden a `glossary.tsv` con la marca `l`; luego `check --rule glossary` localiza lo que hay que revisar.

## Limpieza de la cola

`work_queue/` acumula restos: lotes terminados, textos apartados en `manual/`, registros… `python tools/pod.py clean` los limpia sin tocar nunca trabajo pendiente. El cierre de los agentes lo ejecuta siempre; a mano, `--dry-run` muestra antes qué haría.

| Qué | Cuándo se borra |
|---|---|
| `manual/` | Los textos que ya se han corregido por otra vía (a mano, con otro agente o en otro lote). Lo que sigue sin resolver se queda y se avisa |
| `todo/` e `index/` | Lotes cuyo contenido entero ya está resuelto por otra vía, y archivos huérfanos (sin su pareja). Un lote con salida pendiente de aplicar no se toca |
| `done/` | Lotes aplicados, ya verificados y con más de `keep_done_days` días (7 por defecto) |
| `applied.jsonl` | Registros ya verificados y con más de `keep_log_days` días (60 por defecto) |
| `changed.json`, `last_sync.json` | Las claves que ya no están pendientes |
| `removed/` | Nunca: son archivos que desaparecieron del inglés y conviene revisarlos a mano |

Los plazos se cambian en `clean` de `config.json`.

**Lo que se queda en `manual/`** (textos que fallaron dos veces la validación) se puede corregir a mano en `spanish/`, y el siguiente `clean` lo quita de la lista. También se puede devolver a la cola con `clean --requeue`: vuelven como lotes **M** y se traducen por el flujo normal, con validación incluida.

Los lotes M van aparte a propósito: **un agente puede ocuparse de `manual/` mientras otro traduce pendientes**, uno con `--prefix M` y otro con `--prefix B`. Las órdenes que escriben (`apply`, `fix`, `batch`, `sync`, `clean`, `setaside`) se turnan mediante un bloqueo, así que no se pisan. Lo que no conviene es lanzar dos agentes **con el mismo prefijo**: ambos cogerían el mismo lote y uno traduciría para nada.

## Trabajar con un agente

La sesión se abre **en la carpeta del proyecto**: así Claude Code carga `AGENTS.md` a través de `CLAUDE.md` (otros agentes, como Cursor o Codex, leen `AGENTS.md` directamente). Basta con una de estas frases:

1. **Actualización:** «Ha salido una actualización de Princes of Darkness y ya he commiteado el inglés nuevo en `english/`. Traduce lo nuevo de la actualización siguiendo `AGENTS.md`. No toques git.»
2. **Pendientes:** «Traduce pendientes siguiendo `AGENTS.md`. Máximo 15 lotes. No toques git.» Para forzar una zona: «…pendientes de `<carpeta>/*`…».
3. **Mejoras:** «Revisa y mejora lo traducido siguiendo `AGENTS.md`: ejecuta `fix` y luego la revisión con la regla `glossary`. Máximo 15 lotes. No toques git.»
4. **Nombres:** «Adapta los nombres de personajes y dinastías siguiendo `AGENTS.md`. No toques git.»

El agente termina siempre con el cierre (`fix --dirty`, `verify`, `clean` y un resumen) y nunca ejecuta `build` ni toca git.

Varias sesiones pueden trabajar a la vez si cada una se ocupa de un rango distinto de lotes: `apply` bloquea la cola mientras escribe.

### Agente local (Jan)

`tools/local_agent.py` hace el bucle de `TRADUCIR_LOTE.md` con un modelo local, sin que este tenga que ejecutar órdenes: pide el lote con `next`, envía `TRADUCIR_LOTE.md` y el lote al modelo, guarda la respuesta en `work_queue/out/` y ejecuta `apply`. Los rechazos siguen el mismo camino (reintento → `manual/`).

**Menú:** `python tools/menu.py` ofrece Actualizar · Traducir pendientes · Corregir · Seguir con la cola · Estado · Limpiar la cola. Hace los pasos 3 y 4: prepara los lotes, comprueba que Jan responde, permite elegir el modelo de una lista (y descarga de Jan los demás que estén cargados, para no ocupar la GPU), lanza el agente y termina con el cierre. Los pasos siguientes describen lo que hace por dentro.

1. **Una vez, en Jan:** en la configuración del modelo, *Context Size* = 16384. En Ajustes → llama.cpp, *Parallel Sequences* = 1 y *Unified KV Cache* activado (Jan reserva un hueco extra para sus tareas internas y, sin caché unificada, cada petición solo tendría la mitad del contexto).
2. **Arrancar:** activar Ajustes → Local API Server (127.0.0.1:1337). Con el menú no hace falta cargar el modelo a mano; sin el menú, hay que cargar uno (y solo uno): el script usa el que esté cargado y se niega a seguir si hay varios, porque Jan carga cualquier modelo que se le pida aunque ya haya otro en marcha.
3. **Preparar lotes:** con `sync` / `batch`, como en los modos anteriores.
4. **Traducir:** `python tools/local_agent.py --prefix B --limit 10 --close`
   - `--dry-run`: traduce el siguiente lote y lo muestra sin guardar nada.
   - `--close`: hace «el cierre» (`fix --dirty`, `verify --batch`, una pasada R, `clean` y `status`).
   - `--model`: forzar un modelo concreto de Jan. `--url`: otro servidor compatible con OpenAI.
5. **(Usuario)** Revisa el diff de `spanish/`, con especial atención al estilo, la concordancia y la terminología.

**Si un lote falla entero** (no cabe en el contexto, el modelo no devuelve líneas `N = …`, se agota el tiempo), el script no se detiene: divide el lote en dos mitades y las prueba enseguida; si falla un único texto, lo manda a `work_queue/manual/` (`pod.py setaside` hace este apartado). Se detiene solo en dos casos: si Jan no responde (el lote se queda intacto en `todo/`) o si fallan 8 lotes seguidos sin ningún acierto entre medias, señal de un problema general del modelo o del servidor.

## Guía de uso rápida

Todas las órdenes se ejecutan desde la raíz del repositorio (`python tools/pod.py -h` para la ayuda).

| Para… | Orden |
|---|---|
| Ver el progreso y el reparto por línea de juego | `python tools/pod.py status --top 25` |
| Simular una actualización | `python tools/pod.py sync --dry-run` |
| Aplicar una actualización | `python tools/pod.py sync` |
| Preparar solo lo nuevo | `python tools/pod.py batch --scope update` |
| Preparar pendientes (en orden de prioridad) | `python tools/pod.py batch --limit 5` |
| Preparar pendientes de una zona concreta | `python tools/pod.py batch --files "<carpeta>/*" --limit 5` |
| Preparar nombres de personajes y dinastías | `python tools/pod.py batch --mode names` |
| Ver el siguiente lote | `python tools/pod.py next --show` |
| Aplicar la traducción de un lote | `python tools/pod.py apply B0001` |
| Limpiar sin IA (simulación) | `python tools/pod.py fix --dry-run` |
| Limpiar sin IA | `python tools/pod.py fix` (con `--dirty`, solo lo modificado) |
| Buscar defectos | `python tools/pod.py check --rule tokens --examples 3` |
| Preparar la corrección de esos defectos | `python tools/pod.py batch --mode review --rule tokens` |
| Auditar lo que hizo un agente | `python tools/pod.py verify --all` |
| Limpiar la cola | `python tools/pod.py clean` (`--dry-run` para simular) |
| Devolver a la cola lo que quedó en `manual/` | `python tools/pod.py clean --requeue` (vuelven como lotes **M**) |
| Volcar el mod y subir versión | `python tools/pod.py build --version X.Y.Z --sync-supported` (también actualiza la versión de PoD de este README) |
| Regenerar el glosario del mod | `python tools/pod.py glossary` |

Notas:

- Un lote son 40 textos (200 en el modo nombres); `--limit` cuenta lotes, no textos.
- Sin `--rule`, `check` y `batch --mode review` pasan todas las reglas.
- Para traducir un lote a mano: `next --show`, escribir `work_queue/out/<LOTE>.txt` con una línea `1 = texto` por elemento y aplicar con `apply <LOTE>`. Un lote solo sale de la cola cuando se aplica su salida.
- Las claves nuevas que mete `sync` se quedan en inglés hasta que se traducen; `build` las publica en inglés entretanto, sin romper nada.
- Las cifras actuales (claves hechas, pendientes y reparto) las da `status`.
