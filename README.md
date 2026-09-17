# Princes of Darkness · Traducción al castellano

Mod de traducción al castellano de España de *Princes of Darkness* para Crusader Kings III (Steam Workshop 3303353422).

> **¿Eres un agente o una IA y te han pedido traducir, revisar o actualizar?** Empieza por **[AGENTS.md](AGENTS.md)** (qué hacer según el encargo) y luego lee **[tools/TRADUCIR_LOTE.md](tools/TRADUCIR_LOTE.md)** (cómo traducir un lote). Tu trabajo termina en `working/spanish`: no edites los `.yml` a mano, no ejecutes `build` ni toques `spanish_translation/`, y no uses git para modificar el repositorio.

## Documentación

| Archivo | Para quién | Contenido |
|---|---|---|
| `README.md` | Personas | Este documento: el flujo completo |
| `AGENTS.md` (+ `CLAUDE.md`, que lo importa) | Agentes | **Qué** hacer: normas y una receta por encargo |
| `tools/TRADUCIR_LOTE.md` | Agente traductor | **Cómo** traducir un lote: bucle, idioma, marcas del juego, género, nombres |

## Flujo

Los scripts hacen todo lo mecánico y el modelo barato (Haiku) solo traduce textos sueltos. Un script valida cada respuesta antes de escribirla, así que un error del modelo nunca rompe un archivo.

```
original_text/english ──sync──► working/spanish ──batch──► work_queue/todo/U0001.txt
                                      ▲                              │  (agente: tools/TRADUCIR_LOTE.md)
                                      └──────apply (valida)◄─ work_queue/out/U0001.txt
working/spanish ──build──► spanish_translation (Steam)
```

Se mantiene la convención de siempre: un archivo con cabecera `l_english` dentro de `working/spanish` está sin traducir. `apply` la cambia a `l_spanish:` cuando el archivo queda completo. Las carpetas `working/cambiar_sufijo…` y `working/cambiar_clave…` ya no hacen falta (`sync` y `build` hacen su trabajo).

Prefijos de lote: **U** = actualización · **B** = pendientes · **R** = revisión · **N** = nombres.

## Piezas

| Archivo | Qué es |
|---|---|
| `tools/pod.py` | Script único (solo biblioteca estándar). `python tools/pod.py -h` |
| `tools/config.json` | Rutas, tamaño de lote, prioridades, archivos que no se traducen, último commit sincronizado |
| `tools/glossary.tsv` | Glosario oficial (VEO20 / CK3 / pendiente de verificar). Se edita a mano |
| `tools/glossary_mod.tsv` | Generado con `pod.py glossary` desde los conceptos ya traducidos del mod |
| `tools/keep_english.txt` | Claves que se quedan en inglés; `apply` lo amplía solo |
| `work_queue/` | Cola de lotes (no se versiona): `todo/`, `out/`, `index/`, `done/`, `manual/`, `changed.json`, `last_sync.json` |

Cada lote solo lleva las entradas del glosario que aparecen en sus textos. Los textos repetidos se traducen una sola vez. Lo que ya está traducido en otra clave con el mismo texto se rellena sin IA (memoria de traducción).

## Modo 1 · Actualización de PoD

1. Copias el inglés de la PoD de Workshop a `original_text/english` y haces commit.
2. `python tools/pod.py sync --dry-run` → revisas qué va a cambiar.
3. `python tools/pod.py sync` → hace lo siguiente:
   - Archivos nuevos: se copian con cabecera `l_english`.
   - Claves nuevas: se insertan en su sitio, en inglés.
   - Claves cuyo inglés ha cambiado: se ponen en inglés y la traducción antigua se guarda en `changed.json`, para que el agente la reutilice.
   - Claves borradas en origen: se eliminan.
   - Claves que solo existen en español: se dejan y solo se avisa.
   - `--prune` mueve a `work_queue/removed/` los archivos que ya no existen en inglés.
4. `python tools/pod.py batch --scope update` (solo lo que trajo el `sync`, registrado en `work_queue/last_sync.json`) y el agente procesa los lotes U.
5. **(Tú)** Revisas el diff de `working/spanish`.
6. **(Tú)** `python tools/pod.py build --version 0.x.y --sync-supported` → carpeta de Steam lista, y commit. Los agentes nunca hacen `build` ni tocan git.

## Modo 2 · Pendientes

`python tools/pod.py status` → `python tools/pod.py batch [--files "traits/*"] [--limit 20]` → agente → (tú) `build`.

Orden por defecto: conceptos → rasgos → interfaz → interacciones → decisiones → … → eventos al final (`priority` en `config.json`). Nombres de personajes: `batch --mode names` (solo se adaptan los que tienen forma española consolidada). Las dinastías no se traducen.

## Modo 3 · Mejoras

1. `python tools/pod.py fix --dry-run` y después `fix`: arreglos seguros sin IA (dobles espacios, `GetCustom('ES_O')`, `| E]`).
2. `python tools/pod.py check [--rule R] [--files …]` → informe. Reglas:
   - `tokens`: marcas del juego perdidas o cambiadas.
   - `custom`: funciones de género inexistentes.
   - `spaces`: espacios sobrantes.
   - `punct`: faltan ¿ o ¡.
   - `glossary`: término del glosario no respetado; solo usa las entradas marcadas con `l`.
   - `display`: texto de `Glossary(...)` o `Concept(...)` sin traducir.
   - `english`: palabras inglesas sueltas.
3. `python tools/pod.py batch --mode review --rule R` → el agente devuelve solo las líneas que corrige → (tú) `build`.

Los cambios terminológicos globales (p. ej. Hambre → Ansia) se deciden antes y se añaden a `glossary.tsv` con la marca `l`; luego `check --rule glossary` genera los lotes de revisión.

## Cómo lanzar el agente

Abre la sesión **en la carpeta del proyecto** (Claude Code carga `AGENTS.md` a través de `CLAUDE.md`) y pide el encargo en lenguaje normal:

- «Traduce lo nuevo de la actualización» → `sync` → `batch --scope update` → lotes **U** (el agente termina en `working/spanish`; `build`, versión y git son cosa tuya)
- «Traduce los pendientes de traits» → `batch --files "traits/*"` → lotes **B**
- «Revisa el glosario en los eventos» → `check` / `batch --mode review` → lotes **R**
- «Adapta los nombres de personajes» → `batch --mode names` → lotes **N**

Formas de trabajar:
- **Sesión con Haiku:** no pases de 15 lotes por sesión y abre una nueva para seguir.
- **Sesión con un modelo mayor:** prepara los lotes y reparte rangos entre subagentes Haiku. Pueden trabajar en paralelo porque `apply` bloquea la cola.
- **Otros agentes** (Cursor, Codex…): leen `AGENTS.md` directamente.

Lo que falla dos veces va a `work_queue/manual/`.

## Volumen (septiembre de 2026)

- Pendiente: ~29 600 textos únicos, ~3,6 M caracteres en inglés (~0,9 M tokens), ~830 lotes de 40 textos.
- La memoria de traducción rellenó 1 707 claves sin coste.
- Revisión inicial: ~500 líneas con marcas rotas, ~960 avisos de glosario, ~530 textos de Glossary sin traducir, 50 Custom de género rotos.
