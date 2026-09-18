# Princes of Darkness · Traducción al castellano

Mod de traducción al castellano de España de *Princes of Darkness* para Crusader Kings III (Steam Workshop 3303353422).

> **Para agentes e IA:** el punto de partida es **[AGENTS.md](AGENTS.md)** (qué hacer según el encargo) y, para traducir, **[tools/TRADUCIR_LOTE.md](tools/TRADUCIR_LOTE.md)**. El trabajo de un agente termina en `working/spanish`: nada de editar `.yml` a mano, ejecutar `build`, tocar `spanish_translation/` ni modificar el repositorio con git.

## Documentación

| Archivo | Para quién | Contenido |
|---|---|---|
| `README.md` | Personas | Este documento: el flujo completo y la guía de uso |
| `AGENTS.md` (y `CLAUDE.md`, que lo importa) | Agentes | **Qué** hacer: normas y una receta por encargo |
| `tools/TRADUCIR_LOTE.md` | Agente traductor | **Cómo** traducir un lote: bucle, idioma, marcas del juego, género, nombres |

## Cómo funciona

Los scripts hacen todo lo mecánico y el modelo barato (Haiku) solo traduce textos sueltos. Un script valida cada respuesta antes de escribirla, así que un error del modelo nunca rompe un archivo.

```
original_text/english ──sync──► working/spanish ──batch──► work_queue/todo/U0001.txt
                                      ▲                              │  (agente: tools/TRADUCIR_LOTE.md)
                                      └──────apply (valida)◄─ work_queue/out/U0001.txt
working/spanish ──build──► spanish_translation (Steam)
```

- **Marca de «sin traducir»:** un archivo de `working/spanish` con nombre `_l_spanish.yml` y cabecera `l_english` está pendiente. `apply` cambia la cabecera a `l_spanish:` cuando el archivo queda completo.
- **Prefijos de lote:** **U** = actualización · **B** = pendientes · **R** = revisión · **N** = nombres.
- **Ahorro:** cada lote lleva solo las entradas del glosario que aparecen en sus textos; los textos repetidos se traducen una vez, y lo que ya está traducido en otra clave con el mismo texto se rellena sin IA (memoria de traducción).
- **Rechazos:** lo que no pasa la validación vuelve en un lote de reintento con el motivo; si falla dos veces, va a `work_queue/manual/`.

| Pieza | Qué es |
|---|---|
| `tools/pod.py` | Script único (solo biblioteca estándar). `python tools/pod.py -h` |
| `tools/config.json` | Rutas, tamaño de lote, orden de prioridad, archivos que no se traducen, último commit sincronizado |
| `tools/glossary.tsv` | Glosario oficial (VEO20 / CK3 / pendiente de verificar). Se edita a mano |
| `tools/glossary_mod.tsv` | Generado con `pod.py glossary` a partir de los conceptos ya traducidos del mod |
| `tools/keep_english.txt` | Claves que se quedan en inglés; `apply` lo amplía solo |
| `work_queue/` | Cola de lotes y registros de trabajo (no se versiona) |

## Modo 1 · Actualización de PoD

1. **(Usuario)** Copia el inglés de la PoD de Workshop a `original_text/english` y hace commit.
2. `python tools/pod.py sync --dry-run` → muestra qué va a cambiar.
3. `python tools/pod.py sync`:
   - Archivos nuevos: se copian a `working/spanish` renombrados y con cabecera `l_english`.
   - Claves nuevas: se insertan en su sitio, en inglés.
   - Claves cuyo inglés ha cambiado: se ponen en inglés y la traducción antigua se guarda para que el agente la reutilice.
   - Claves borradas en origen: se eliminan. Las que solo existen en español se dejan y se avisa.
   - Con `--prune`, los archivos que ya no existen en inglés se mueven a `work_queue/removed/`.
4. `python tools/pod.py batch --scope update` → lotes **U** solo con lo que trajo el `sync`.
5. El agente traduce los lotes y cierra con `fix --dirty` y `verify --batch` (ver «El cierre» en `AGENTS.md`).
6. **(Usuario)** Revisa el diff de `working/spanish`, ejecuta `build` con la versión nueva y hace commit.

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
   - `punct`: faltan ¿ o ¡.
   - `glossary`: término del glosario no respetado (solo entradas marcadas con `l`).
   - `display`: texto de `Glossary(...)` o `Concept(...)` sin traducir.
   - `english`: palabras inglesas sueltas.
3. `python tools/pod.py batch --mode review --rule R` → lotes **R**; el agente devuelve solo las líneas que corrige → `build` (usuario).

`check` mira archivos completos, defectos antiguos incluidos. `verify` mira solo las claves escritas por los lotes aplicados (desde la última verificación, o todas con `--all`): sirve para auditar el trabajo de un agente sin mezclarlo con lo anterior.

Los cambios terminológicos globales (p. ej. Hambre → Ansia) se deciden antes y se añaden a `glossary.tsv` con la marca `l`; luego `check --rule glossary` localiza lo que hay que revisar.

## Trabajar con un agente

La sesión se abre **en la carpeta del proyecto**: así Claude Code carga `AGENTS.md` a través de `CLAUDE.md` (otros agentes, como Cursor o Codex, leen `AGENTS.md` directamente). Basta con una de estas frases:

1. **Actualización:** «Ha salido una actualización de Princes of Darkness y ya he commiteado el inglés nuevo en `original_text`. Traduce lo nuevo de la actualización siguiendo `AGENTS.md`. No toques git.»
2. **Pendientes:** «Traduce pendientes siguiendo `AGENTS.md`. Máximo 15 lotes. No toques git.» Para forzar una zona: «…pendientes de `<carpeta>/*`…».
3. **Mejoras:** «Revisa y mejora lo traducido siguiendo `AGENTS.md`: ejecuta `fix` y luego la revisión con la regla `glossary`. Máximo 15 lotes. No toques git.»
4. **Nombres:** «Adapta los nombres de personajes y dinastías siguiendo `AGENTS.md`. No toques git.»

El agente termina siempre con el cierre (`fix --dirty`, `verify` y un resumen) y nunca ejecuta `build` ni toca git.

- **Con Haiku:** un máximo de 15 lotes por sesión; para seguir, sesión nueva.
- **Con un modelo mayor:** puede preparar los lotes y repartir rangos entre subagentes Haiku en paralelo (`apply` bloquea la cola).

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
| Volcar el mod y subir versión | `python tools/pod.py build --version 0.3.17 --sync-supported` |
| Regenerar el glosario del mod | `python tools/pod.py glossary` |

Notas:

- Un lote son 40 textos (200 en el modo nombres); `--limit` cuenta lotes, no textos.
- Sin `--rule`, `check` y `batch --mode review` pasan todas las reglas.
- Para traducir un lote a mano: `next --show`, escribir `work_queue/out/<LOTE>.txt` con una línea `1 = texto` por elemento y aplicar con `apply <LOTE>`. Un lote solo sale de la cola cuando se aplica su salida.
- Las claves nuevas que mete `sync` se quedan en inglés hasta que se traducen; `build` las publica en inglés entretanto, sin romper nada.
- Las cifras actuales (claves hechas, pendientes y reparto) las da `status`.
