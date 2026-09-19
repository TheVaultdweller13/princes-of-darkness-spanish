# Instrucciones para traducir lotes (Princes of Darkness → castellano)

Eres un traductor. Solo traduces textos de lotes ya preparados: no edites ningún archivo aparte de tus salidas en `work_queue/out/`, no ejecutes más órdenes que `python tools/pod.py …` (nunca `build`) y nunca uses git. Qué preparar según el encargo y cómo cerrar el trabajo está en `AGENTS.md`; no necesitas leer nada más.

## Bucle de trabajo

`X` es el prefijo del encargo (U = actualización, B = pendientes, R = revisión, N = nombres). Si no te han dado ninguno, omite `--prefix`.

1. `python tools/pod.py next --prefix X` → te dice el siguiente lote (`work_queue/todo/X0001.txt`). Si dice `NO QUEDAN LOTES`, termina.
2. Lee ese archivo entero.
3. Escribe `work_queue/out/X0001.txt` con una línea por elemento:
   ```
   1 = texto traducido
   2 = texto traducido
   ```
   - Una sola línea por número, sin comillas alrededor y sin comentarios.
   - En modo REVISAR escribe solo las líneas que cambies (o `# sin cambios`).
4. `python tools/pod.py apply X0001`
   - Si hay rechazos (`✘`), se crea un lote de reintento con el mismo prefijo y solo esos elementos. El motivo del rechazo está en `MOTIVO:`; corrígelo en el reintento.
5. Vuelve al paso 1. Al quedarte sin lotes, al llegar al límite que te hayan dado o tras 15 lotes, pasa a «el cierre» de `AGENTS.md`.

## Reglas de idioma

- Castellano de España, registro literario y sombrío (ambientación medieval y vampírica). Usa tú/vosotros, nunca "ustedes" como plural de confianza.
- Respeta SIEMPRE el glosario que aparece en la cabecera del lote; tiene prioridad sobre tu criterio.
- Mayúsculas como en español: en títulos, solo la primera palabra y los nombres propios ("Traición de sangre", no "Traición De Sangre"). Excepción: los términos del glosario van tal cual (Clanes, Disciplinas, Príncipe, Abrazo, Frenesí, Letargo…).
- Nombres de Clanes: Brujah, Gangrel, Lasombra, Malkavian, Nosferatu, Ravnos, Salubri, Toreador, Tremere, Tzimisce, Ventrue y Baali no cambian. Assamite → Assamita, Cappadocian → Capadocio.
- Nombres propios de personas, lugares y dinastías no se traducen, salvo que exista una forma española habitual (Jerusalem → Jerusalén, Constantinople → Constantinopla).
- Si un texto debe quedarse igual (nombre propio, latín, siglas), cópialo tal cual: el sistema lo recordará.
- Diálogos y citas entre comillas latinas «así». Signos de apertura ¿ y ¡ siempre.
- No toques los números: déjalos exactamente como en el original.
- `EN-ANTIGUO` / `ES-ANTIGUO` indican que el inglés ha cambiado. Reutiliza la traducción antigua y cambia solo lo que haya cambiado.

## Marcas del juego: cópialas EXACTAMENTE igual

El validador rechaza la línea si falta, sobra o cambia cualquiera de estas marcas:

| Marca | Ejemplo | Regla |
|---|---|---|
| Variables | `$VALUE$`, `$EFFECT_LIST_BULLET$` | copiar igual |
| Funciones | `[ROOT.Char.GetShortUIName]`, `[GetPlayer.GetName]` | copiar igual |
| Conceptos | `[prestige|E]`, `[stress_i]` | copiar igual (el juego ya pone el nombre en español) |
| Concepto con texto | `[Concept('domicile','Hideout')|E]` | traduce SOLO el segundo texto: `[Concept('domicile','Escondite')|E]` |
| Glosario con texto | `[Glossary('Disciplines','game_concept_discipline_desc')]` | traduce SOLO el PRIMER texto: `[Glossary('Disciplinas','game_concept_discipline_desc')]` |
| Umbra con texto | `[UmbraGlossaryLocalized('shadowlands','Underworld')]` | traduce SOLO el segundo texto: `[UmbraGlossaryLocalized('shadowlands','Inframundo')]` |
| Formato | `#V 15#!`, `#bold texto#!`, `#F …#!` | copiar `#V`, `#bold`, `#!`; traducir el texto de dentro. `#!` solo cierra el formato: **no es una exclamación**, no añadas «¡» ni «!» por él |
| Iconos | `@sorcerer_icon!` | copiar igual |
| Salto de línea | `\n` | copiar igual, mismo número de veces |

- Puedes cambiar solo el indicador de mayúscula de una función (`|U` ↔ nada) para adaptarlo a la frase española.
- Pronombres ingleses del juego (`GetHerHis`, `GetSheHe`, `GetHerHim`, `GetHerselfHimself`, `GetHersHis`, `GetLadyLord`, `GetWomanMan`): puedes quitarlos o cambiarlos. Ej.: `[recipient.GetHerHis] sword` → `su espada`; `[ROOT.Char.GetSheHe] is` → se omite el sujeto o se usa `[ROOT.Char.Custom('ES_ElElla')]`.

## Género (concordancia con personajes)

Para adjetivos o artículos que dependen del sexo de un personaje, puedes AÑADIR estas funciones del juego oficial (son las únicas marcas extra permitidas). Usa el mismo personaje que aparezca en la frase (`ROOT.Char`, `CHARACTER`, `TARGET_CHARACTER`…):

| Función | Resultado (hombre/mujer) | Ejemplo |
|---|---|---|
| `[X.Custom('ES_OA')]` | o / a | `Aterrad[ROOT.Char.Custom('ES_OA')]` |
| `[X.Custom('ES_OsAs')]` | os / as | |
| `[X.Custom('ES_ElLa')]` | el / la | |
| `[X.Custom('ES_DelDela')]` | del / de la | |
| `[X.Custom('ES_AlAla')]` | al / a la | |
| `[X.Custom('ES_XA')]` | (nada) / a | `Un[X.Custom('ES_XA')]` → Un / Una |
| `[X.Custom('ES_EA')]` | e / a | |
| `[X.Custom('ES_LoLa')]` | lo / la | |
| `[X.Custom('ES_ElElla')]` | él / ella | |
| `[X.Custom('ES_HijoHija')]` | hijo / hija | |
| `[X.Custom('ES_SennorSennora')]` | señor / señora | |

Si no sabes a qué personaje se refiere, redacta la frase de forma neutra en vez de adivinar.

## Modo NOMBRES

Lotes con nombres de personajes y de dinastías. Por defecto NO se traducen. Devuelve solo los que tienen una forma española consolidada, normalmente personajes históricos, míticos o bíblicos:
- `Helena of Troy` → `Helena de Troya` · `Menelaus` → `Menelao` · `Charlemagne` → `Carlomagno` · `Justinian` → `Justiniano` · `Cain` → `Caín`
- Traduce también los epítetos y los «of X» con lugar conocido: `Helen of Genoa` → `Helena de Génova`.
- NO adaptes nombres corrientes sin fama propia (`Hadmar`, `Aliu`, `Fakhr al-Din`), ni nombres de vampiros inventados por el mod, aunque exista el equivalente español (no pongas `Juan` por `John`).
- Dinastías: igual criterio. Solo las históricas con forma castellana asentada (`Komnenos` → `Comneno`, `Plantagenet` → `Plantagenet`, `Capet` → `Capeto`); las inventadas por el mod se quedan como están.
- Si dudas, déjalo igual (no lo escribas).

## Ejemplos

```
EN: [ROOT.Char.GetShortUIName|U] has been Embraced by a #V Tremere#!.
1 = [ROOT.Char.GetShortUIName|U] ha sido Abrazad[ROOT.Char.Custom('ES_OA')] por un #V Tremere#!.

EN: Gain #V $VALUE$#! [prestige|E]\n$EFFECT_LIST_BULLET$Lose a [hook|E]
2 = Ganas #V $VALUE$#! de [prestige|E]\n$EFFECT_LIST_BULLET$Pierdes un [hook|E]

EN: "Leave us, mortal."
3 = «Déjanos, mortal».
```
