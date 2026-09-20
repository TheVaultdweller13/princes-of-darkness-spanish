#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta única para la traducción de Princes of Darkness (CK3) al castellano.
Solo librería estándar. Ejecutar desde cualquier sitio: python tools/pod.py <orden>

Órdenes:
  status                     Progreso real por clave y estado de la cola.
  sync [--base C] [--dry-run] [--prune]
                             Aplica una actualización del inglés (english/) sobre spanish/:
                             archivos nuevos, claves nuevas, claves con inglés cambiado, claves borradas.
  batch [--mode pending|review|names] [--scope all|update] [--rule R] [--files GLOB] [--limit N] [--no-tm]
                             Crea lotes para el agente traductor en work_queue/todo (y autocompleta con memoria de traducción).
  next [--prefix U|B|R|N]    Muestra el siguiente lote pendiente (lo que tiene que hacer el agente).
  apply [LOTE ...|--all]     Valida las salidas de work_queue/out y las escribe en spanish/.
  check [--files GLOB]       Informe de problemas (tokens, glosario, espacios, ¿¡, Custom ES_...).
  build [--version X] [--sync-supported]
                             Regenera mod/localization/spanish para publicar.
  fix [--dry-run] [--dirty] [--files GLOB]
                             Arreglos automáticos sin IA (dobles espacios, GetCustom('ES_O'), "| E]", "Concept (", comillas sin cerrar).
  verify [--all] [--batch]   Revisa solo las claves escritas por los lotes ya aplicados (--batch crea lotes R para corregirlas).
  glossary                   Regenera tools/glossary_mod.tsv a partir de los conceptos del mod ya traducidos.
  setaside LOTE [--split] [--reason R]
                             Aparta un lote que ha fallado entero: lo divide en dos (--split) o lo manda a manual/.
  clean [--dry-run] [--requeue]
                             Limpia work_queue: quita de manual/ lo ya corregido, lotes obsoletos y huérfanos,
                             lotes terminados antiguos y registros caducados. --requeue devuelve manual/ a la cola.
"""
import argparse, fnmatch, json, re, shutil, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
CFG_PATH = TOOLS / "config.json"
CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
EN_DIR = ROOT / CFG["en_dir"]
ES_DIR = ROOT / CFG["es_dir"]
Q = ROOT / CFG["queue_dir"]
BOM = "﻿"

# ---------------------------------------------------------------- parseo

KV_RE = re.compile(r'^(\s*)([^\s#:"]+):(\d*)(\s*)"(.*)$')
HDR_RE = re.compile(r'^\s*(l_\w+):\s*$')


class Loc:
    """Archivo de localización conservando cada línea tal cual."""

    def __init__(self, path, text=None):
        self.path = path
        if text is None:
            text = path.read_bytes().decode("utf-8-sig", errors="replace")
        text = text.lstrip(BOM)
        self.eol = "\r\n" if "\r\n" in text else "\n"
        self.final_eol = text.endswith(("\n", "\r"))
        self.lines = []  # dicts
        self.header = None
        seen = Counter()
        for raw in text.splitlines():
            ln = {"raw": raw, "kind": "other"}
            m = KV_RE.match(raw)
            h = HDR_RE.match(raw)
            if h and self.header is None:
                ln["kind"] = "header"
                self.header = h.group(1)
            elif m:
                rest = m.group(5)
                value, tail, unclosed = rest, "", True
                for i in range(len(rest) - 1, -1, -1):
                    if rest[i] == '"':
                        after = rest[i + 1:]
                        if after.strip() == "" or after.lstrip().startswith("#"):
                            value, tail, unclosed = rest[:i], after, False
                            break
                key = m.group(2)
                ln.update(kind="kv", indent=m.group(1), key=key, ver=m.group(3), sep=m.group(4),
                          value=value, tail=tail, unclosed=unclosed, occ=seen[key])
                seen[key] += 1
            self.lines.append(ln)

    def kvs(self):
        return [l for l in self.lines if l["kind"] == "kv"]

    def index(self):
        return {(l["key"], l["occ"]): l for l in self.kvs()}

    @staticmethod
    def render(ln):
        if ln["kind"] != "kv" or "dirty" not in ln:
            return ln["raw"]
        return f'{ln["indent"]}{ln["key"]}:{ln["ver"]}{ln["sep"]}"{ln["value"]}"{ln["tail"]}'

    def set_value(self, ln, value):
        ln["value"] = value
        ln["dirty"] = True

    def set_header(self, lang):
        for ln in self.lines:
            if ln["kind"] == "header":
                ln["raw"] = re.sub(r"l_\w+", lang, ln["raw"], count=1)
                self.header = lang
                return

    def text(self):
        body = self.eol.join(self.render(l) for l in self.lines)
        return BOM + body + (self.eol if self.final_eol else "")

    def save(self, path=None):
        path = path or self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.text().encode("utf-8"))


def es_rel(en_rel):
    p = Path(en_rel)
    return str(p.with_name(p.name.replace("l_english", "l_spanish"))).replace("\\", "/")


def en_files():
    return sorted(str(p.relative_to(EN_DIR)).replace("\\", "/") for p in EN_DIR.rglob("*.yml"))


# ---------------------------------------------------------------- tokens y validación

# Funciones con un argumento de texto visible (traducible): nombre → posición del texto
DISPLAY_ARG = {"Concept": 1, "Glossary": 0, "UmbraGlossaryLocalized": 1}
TWO_ARG_RE = re.compile(r"\[(\w+)\('([^']*)'\s*,\s*'([^']*)'\)")
# «#!» solo cierra el formato: la palabra que pueda ir pegada detrás («#!Shows») es texto normal
TOKEN_RE = re.compile(r"\[[^\[\]]*\]|\$[^$\s]+\$|@[\w]+!|#!|#[A-Za-z_][\w;]*|\\n")
ES_CUSTOM_RE = re.compile(r"\[[\w.:]+\.(Get)?Custom\('(ES_\w+)'\)(\|\w+)?\]")
# Pronombres ingleses del juego: en español se pueden omitir o añadir libremente
# (\s* tolera el espacio de más que trae a veces el mod original: [CHARACTER. GetHerHim])
GENDER_GETTER_RE = re.compile(r"\[[\w.:()']+\.\s*(GetHerHis|GetSheHe|GetHerHim|GetHerselfHimself|GetLadyLord|GetWomanMan|GetHersHis)(\|\w*)?\]")


def display_args(s):
    """Textos visibles dentro de Concept/Glossary/UmbraGlossaryLocalized."""
    return [m.group(2 + DISPLAY_ARG[m.group(1)]) for m in TWO_ARG_RE.finditer(s) if m.group(1) in DISPLAY_ARG]
_vanilla_es = None


def vanilla_es_customs():
    global _vanilla_es
    if _vanilla_es is None:
        # Copia guardada en config por si el juego no es accesible (p. ej. entorno aislado)
        _vanilla_es = set(CFG.get("extra_es_customs", [])) | set(CFG.get("es_customs_cache", []))
        d = Path(CFG["vanilla_custom_loc"])
        if d.is_dir():
            for f in d.rglob("*.txt"):
                _vanilla_es.update(re.findall(r"^\s*(ES_\w+)\s*=", f.read_text(encoding="utf-8-sig", errors="replace"), re.M))
    return _vanilla_es


# Funciones que eligen un texto visible según una condición: sus textos entre comillas se traducen
TEXT_CHOICE_RE = re.compile(r"\b(Select_CString|AddTextIf)\s*\(")
QUOTED_ARG_RE = re.compile(r"(,\s*)'([^']*)'")


def _is_text_literal(v):
    """Texto para el jugador, no código: sin paréntesis inicial, variables, barras ni guiones bajos."""
    return not (v.startswith("(") or "$" in v or "|" in v or "_" in v)


def norm_token(t):
    if t.startswith("[") and TEXT_CHOICE_RE.search(t):
        t = QUOTED_ARG_RE.sub(lambda m: m.group(1) + ("'*'" if _is_text_literal(m.group(2)) else f"'{m.group(2)}'"), t)
        t = re.sub(r"\s+", "", t)  # los espacios dentro de estas funciones no cambian nada en el juego
    if t.startswith("["):
        def wild(m):
            if m.group(1) not in DISPLAY_ARG:
                return m.group(0)
            args = [m.group(2), m.group(3)]
            args[DISPLAY_ARG[m.group(1)]] = "*"
            return f"[{m.group(1)}('{args[0]}','{args[1]}')"
        t = TWO_ARG_RE.sub(wild, t)
        m = re.search(r"\|([A-Za-z]+)\]$", t)
        if m:
            flags = "".join(sorted(set(m.group(1)) - set("UuLl")))
            t = t[: m.start()] + ("|" + flags if flags else "") + "]"
    return t


def tokens(s, es=False):
    s = GENDER_GETTER_RE.sub("", s)
    if es:
        s = ES_CUSTOM_RE.sub("", s)
    return Counter(norm_token(t) for t in TOKEN_RE.findall(s))


def strip_markup(s, repl=" "):
    return re.sub(r"\s+", " ", TOKEN_RE.sub(repl, s))


def translatable(s):
    return re.search(r"[A-Za-z]{2,}", strip_markup(s)) is not None


def token_diff(en, es):
    te, ts = tokens(en), tokens(es, es=True)
    if te == ts:
        return ""
    msg = "tokens distintos"
    falta, sobra = list((te - ts).elements()), list((ts - te).elements())
    if falta:
        msg += " | faltan: " + " ".join(falta)
    if sobra:
        msg += " | sobran: " + " ".join(sobra)
    return msg


def validate(en, es):
    """Devuelve (texto_corregido, [errores])."""
    errs = []
    es = es.strip("\r\n")
    if len(es) >= 2 and es[0] == es[-1] == '"' and not en.startswith('"'):
        es = es[1:-1]
    # espacios: respetar los del inglés en los extremos, quitar dobles que el inglés no tenga
    if "  " not in en:
        es = re.sub(r"(?<=\S) {2,}(?=\S)", " ", es)
    lead = en[: len(en) - len(en.lstrip(" "))]
    trail = en[len(en.rstrip(" ")):]
    es = lead + es.strip(" ") + trail
    if not es.strip() and en.strip():
        errs.append("traducción vacía")
    if "\t" in es or "\n" in es:
        errs.append("contiene tabulador o salto de línea real (usa \\n literal)")
    d = token_diff(en, es)
    if d:
        errs.append(d)
    bad = [m.group(0) for m in ES_CUSTOM_RE.finditer(es) if m.group(1) or m.group(2) not in vanilla_es_customs()]
    if bad:
        errs.append("Custom de género inexistente o mal escrito (usa X.Custom('ES_OA') etc.): " + ", ".join(bad))
    return es, errs


# ---------------------------------------------------------------- glosario y lista de conservar

def load_glossary():
    """De menor a mayor prioridad: glossary_books.tsv (glosarios oficiales en PDF),
    glossary_mod.tsv (conceptos del mod ya traducidos) y glossary.tsv (el nuestro, manda)."""
    rows = {}
    for fname in ("glossary_books.tsv", "glossary_mod.tsv", "glossary.tsv"):
        f = TOOLS / fname
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            en, es = parts[0].strip(), parts[1].strip()
            flags = parts[2].strip() if len(parts) > 2 else ""
            note = parts[3].strip() if len(parts) > 3 else ""
            pat = re.compile(r"(?<![\w'])" + re.escape(en) + r"(?:s|es)?(?![\w])", re.I)
            rows[en.lower()] = {"en": en, "es": es, "flags": flags, "note": note, "re": pat}
    return sorted(rows.values(), key=lambda r: -len(r["en"]))


def cmd_glossary(a):
    """Regenera glossary_mod.tsv con los nombres de conceptos del mod ya traducidos."""
    seen, out = set(), ["# GENERADO por 'pod.py glossary' desde game_POD_concepts. No editar: corrige el concepto o añade la entrada a glossary.tsv."]
    for rel in CFG["concept_files"]:
        en, es = load_pair(rel)
        if not es:
            continue
        idx = es.index()
        for l in en.kvs():
            e = idx.get((l["key"], l["occ"]))
            v = l["value"]
            if (not l["key"].startswith("game_concept_") or l["key"].endswith(("_desc", "_possessive")) or not e
                    or e["value"] == v or len(v) > 40 or TOKEN_RE.search(v) or v.lower() in seen
                    or re.search(r"(ing|ed)$", v)):
                continue
            seen.add(v.lower())
            out.append(f"{v}\t{e['value']}\tm\tconcepto del mod")
    (TOOLS / "glossary_mod.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"glossary_mod.tsv: {len(out) - 1} términos")


def glossary_for(texts, gloss):
    joined = " ".join(texts)
    out, blob = [], strip_markup(joined) + " " + " ".join(display_args(joined))
    for g in gloss:
        if g["re"].search(blob):
            out.append(g)
    # Tope por lote: primero lo nuestro y lo verificado, y dentro de eso los términos más largos,
    # que son los que un modelo tiene menos posibilidades de acertar por su cuenta.
    tope = CFG.get("glossary_max_per_batch", 30)
    if len(out) > tope:
        out.sort(key=lambda g: ("b" in g["flags"], -len(g["en"])))
        out = out[:tope]
    return out


def load_keep():
    f = TOOLS / "keep_english.txt"
    if not f.exists():
        return set()
    return {l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}


def add_keep(keys):
    if not keys:
        return
    cur = load_keep()
    new = sorted(set(keys) - cur)
    if new:
        with open(TOOLS / "keep_english.txt", "a", encoding="utf-8") as fh:
            fh.write("\n".join(new) + "\n")


def match_any(rel, pats):
    return any(fnmatch.fnmatch(rel, p) for p in pats)


# ---------------------------------------------------------------- estado

def load_pair(rel):
    en = Loc(EN_DIR / rel)
    esp = ES_DIR / es_rel(rel)
    es = Loc(esp) if esp.exists() else None
    return en, es


def pending_items(files=None, keep=None):
    """Genera (rel, key, occ, en_value) de claves sin traducir."""
    keep = load_keep() if keep is None else keep
    for rel in en_files():
        if files and not match_any(rel, files):
            continue
        if match_any(rel, CFG.get("keep_files", [])):
            continue
        en, es = load_pair(rel)
        idx = es.index() if es else {}
        for l in en.kvs():
            e = idx.get((l["key"], l["occ"]))
            if e is None or (e["value"] == l["value"] and translatable(l["value"]) and l["key"] not in keep):
                yield rel, l["key"], l["occ"], l["value"]


def queued_ids():
    ids = set()
    for f in (Q / "index").glob("*.json") if (Q / "index").exists() else []:
        for it in json.loads(f.read_text(encoding="utf-8"))["items"].values():
            for t in it["targets"]:
                ids.add(tuple(t))
    return ids


def cmd_status(a):
    keep = load_keep()
    tot = done = 0
    per = []
    hdr_en = 0
    for rel in en_files():
        en, es = load_pair(rel)
        idx = es.index() if es else {}
        if es is None or es.header != "l_spanish":
            hdr_en += 1
        kf = match_any(rel, CFG.get("keep_files", []))
        p = 0
        for l in en.kvs():
            tot += 1
            e = idx.get((l["key"], l["occ"]))
            if e is None or (not kf and e["value"] == l["value"] and translatable(l["value"]) and l["key"] not in keep):
                p += 1
            else:
                done += 1
        if p:
            per.append((p, rel, len(en.kvs())))
    print(f"Claves: {tot}  hechas: {done} ({done / tot:.1%})  pendientes: {tot - done}")
    por_linea = Counter()
    for p, rel, _ in per:
        por_linea[splat_of(rel)[1]] += p
    if por_linea:
        print("Pendientes por línea de juego (orden en que se traducirán):")
        for name, n in sorted(por_linea.items(), key=lambda kv: next((i for i, s2 in enumerate(CFG.get("splat_priority", []), 1) if s2["name"] == kv[0]), 0)):
            print(f"  {n:6d}  {name}")
    print(f"Archivos con pendientes: {len(per)}  ·  con cabecera l_english (o sin archivo): {hdr_en}")
    per.sort(reverse=True)
    for p, rel, n in per[: a.top]:
        print(f"  {p:6d}/{n:<6d} {rel}")
    todo = sorted((Q / "todo").glob("*.txt")) if (Q / "todo").exists() else []
    manual = sum(len(json.loads(f.read_text(encoding="utf-8")))
                 for f in (Q / "manual").glob("*.json")) if (Q / "manual").exists() else 0
    print(f"Cola: {len(todo)} lotes pendientes, {manual} textos para revisión manual")
    base = base_mod_info()
    if base:
        readme = ROOT / "README.md"
        m = re.search(r"<!-- base-version -->(.*?)<!-- /base-version -->", readme.read_text(encoding="utf-8")) if readme.exists() else None
        print(f"Princes of Darkness instalado: {base_version_text(base)}")
        if m and not m.group(1).startswith(base["version"] + " ") and m.group(1) != base["version"]:
            print(f"→ El README dice {m.group(1)}: parece que PoD se ha actualizado. "
                  f"Copia su inglés a {CFG['en_dir']}/, haz commit y ejecuta sync.")


# ---------------------------------------------------------------- sync

def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8")


def cmd_sync(a):
    with QueueLock():
        _sync(a)


def _sync(a):
    base = a.base or CFG["last_synced_en_commit"]
    dirty = git("status", "--porcelain", "--", CFG["en_dir"]).stdout.strip()
    if dirty and not a.dry_run:
        sys.exit(f"{CFG['en_dir']} tiene cambios sin commitear: haz commit antes de sincronizar.")
    head = git("log", "-1", "--format=%h", "--", CFG["en_dir"]).stdout.strip()
    if not head:
        sys.exit(f"git no tiene ningún commit con {CFG['en_dir']}/: haz commit de la carpeta antes de sincronizar.")
    print(f"Sincronizando inglés {base} → {head}{'  (simulación)' if a.dry_run else ''}")
    changed_log = {}
    upd_files, upd_keys = [], defaultdict(list)
    stats = Counter()
    en_now = set(en_files())
    for rel in sorted(en_now):
        esp = ES_DIR / es_rel(rel)
        if not esp.exists():
            stats["archivos nuevos"] += 1
            upd_files.append(rel)
            print(f"  NUEVO  {rel}")
            if not a.dry_run:
                esp.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(EN_DIR / rel, esp)  # conserva cabecera l_english = sin traducir
            continue
        # el inglés del commit base puede estar en una ruta anterior (carpetas renombradas)
        for d in [CFG["en_dir"]] + CFG.get("en_dir_previous", []):
            r = git("show", f"{base}:{d}/{rel}")
            if r.returncode == 0:
                break
        old = Loc(None, r.stdout) if r.returncode == 0 else None
        oidx = old.index() if old else {}
        en = Loc(EN_DIR / rel)
        es = Loc(esp)
        eidx = es.index()
        header_i = next((i for i, l in enumerate(es.lines) if l["kind"] == "header"), -1)
        pos = {id(l): i for i, l in enumerate(es.lines)}
        inserts = defaultdict(list)
        anchor = header_i
        touched = False
        for l in en.kvs():
            kid = (l["key"], l["occ"])
            e = eidx.get(kid)
            if e is None:
                inserts[anchor].append({"raw": l["raw"], "kind": "other"})
                upd_keys[rel].append(list(kid))
                stats["claves nuevas"] += 1
                touched = True
                continue
            anchor = pos[id(e)]
            o = oidx.get(kid)
            if o is not None and o["value"] != l["value"] and e["value"] != l["value"]:
                if e["value"] != o["value"]:
                    changed_log.setdefault(rel, {})[l["key"]] = {"old_en": o["value"], "old_es": e["value"]}
                es.set_value(e, l["value"])
                upd_keys[rel].append(list(kid))
                stats["claves con inglés cambiado"] += 1
                touched = True
        drop = set()
        for kid, e in eidx.items():
            if kid not in en.index():
                if kid in oidx:
                    drop.add(pos[id(e)])
                    stats["claves borradas"] += 1
                    touched = True
                else:
                    stats["claves solo en español (se dejan)"] += 1
        if touched:
            print(f"  CAMBIA {rel}")
            new_lines = list(inserts.get(-1, []))
            for i, ln in enumerate(es.lines):
                if i not in drop:
                    new_lines.append(ln)
                new_lines.extend(inserts.get(i, []))
            es.lines = new_lines
            if not a.dry_run:
                es.save()
    es_expected = {es_rel(r) for r in en_now}
    for p in sorted(ES_DIR.rglob("*.yml")):
        rel_es = str(p.relative_to(ES_DIR)).replace("\\", "/")
        if rel_es not in es_expected:
            stats["archivos que ya no existen en inglés"] += 1
            print(f"  SOBRA  {rel_es}{'  → movido a work_queue/removed' if a.prune and not a.dry_run else ''}")
            if a.prune and not a.dry_run:
                dst = Q / "removed" / rel_es
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), dst)
    for k, v in stats.items():
        print(f"{k}: {v}")
    if not a.dry_run:
        f = Q / "changed.json"
        Q.mkdir(exist_ok=True)
        prev = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        for rel, d in changed_log.items():
            prev.setdefault(rel, {}).update(d)
        f.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
        lf = Q / "last_sync.json"
        last = json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else {"new_files": [], "keys": {}}
        last["new_files"] = sorted(set(last["new_files"]) | set(upd_files))
        for rel, ks in upd_keys.items():
            last["keys"][rel] = sorted({tuple(k) for k in last["keys"].get(rel, [])} | {tuple(k) for k in ks})
        last["commits"] = f"{base}..{head}"
        lf.write_text(json.dumps(last, ensure_ascii=False, indent=1), encoding="utf-8")
        CFG["last_synced_en_commit"] = head
        CFG_PATH.write_text(json.dumps(CFG, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Base actualizada a {head} en tools/config.json")


# ---------------------------------------------------------------- memoria de traducción

def build_tm():
    votes = defaultdict(Counter)
    for rel in en_files():
        en, es = load_pair(rel)
        if not es or es.header != "l_spanish":
            continue
        idx = es.index()
        for l in en.kvs():
            e = idx.get((l["key"], l["occ"]))
            if e and e["value"] != l["value"] and translatable(l["value"]):
                votes[l["value"]][e["value"]] += 1
    return {k: c.most_common(1)[0][0] for k, c in votes.items()}


def write_values(assign, keep_keys=()):
    """assign: {(rel, key, occ): (valor_esperado_actual, nuevo)} → escribe y devuelve archivos tocados."""
    byfile = defaultdict(list)
    for (rel, key, occ), v in assign.items():
        byfile[rel].append((key, occ, *v))
    touched, stale = [], 0
    for rel, items in byfile.items():
        esp = ES_DIR / es_rel(rel)
        es = Loc(esp)
        idx = es.index()
        ok = False
        for key, occ, expect, new in items:
            e = idx.get((key, occ))
            if e is None or e["value"] != expect:
                stale += 1
                continue
            if new != e["value"]:
                es.set_value(e, new)
                ok = True
        if ok:
            es.save()
            touched.append(rel)
    add_keep(keep_keys)
    return touched, stale


def flip_headers(rels):
    keep = load_keep()
    for rel in set(rels):
        esp = ES_DIR / es_rel(rel)
        es = Loc(esp)
        if es.header == "l_spanish":
            continue
        if not any(True for _ in pending_items([rel], keep)):
            es.set_header("l_spanish")
            es.save()
            print(f"  ✔ archivo completo, cabecera → l_spanish: {rel}")


# ---------------------------------------------------------------- lotes

def splat_of(rel):
    """Línea de juego de un archivo, según 'splat_priority' de config.json. 0 = general/compartido."""
    low = rel.lower()
    for i, s in enumerate(CFG.get("splat_priority", []), start=1):
        if re.search(s["match"], low):
            return i, s["name"]
    return 0, "general"


def batch_order(rel):
    """Ordena por línea de juego (general primero) y, dentro de cada una, por tipo de archivo."""
    n = len(CFG["priority"])
    cat = n
    for i, p in enumerate(CFG["priority_last"]):
        if fnmatch.fnmatch(rel, p):
            cat = n + 1 + i
            break
    else:
        for i, p in enumerate(CFG["priority"]):
            if fnmatch.fnmatch(rel, p):
                cat = i
                break
    return (splat_of(rel)[0], cat)


PREFIX = {"pending": "B", "update": "U", "review": "R", "names": "N", "manual": "M"}
PREFIXES = "BURNM"  # B pendientes · U actualización · R revisión · N nombres · M devueltos de manual/


def next_batch_name(prefix="B"):
    """Prefijos: U = actualización, B = pendientes, R = revisión, N = nombres. Numeración común."""
    Q.mkdir(exist_ok=True)
    existing = [int(m.group(1)) for p in Q.rglob("*.*") if (m := re.match(rf"[{PREFIXES}](\d{{4}})", p.name))]
    return f"{prefix}{(max(existing) + 1 if existing else 1):04d}"


HEAD_PENDING = """# LOTE {name} · MODO TRADUCIR · {n} elementos
# Lee tools/TRADUCIR_LOTE.md si no lo has leído. Traduce cada EN al castellano (España).
# Salida: crea work_queue/out/{name}.txt con UNA línea por elemento:  <número> = <traducción>
# Luego ejecuta:  python tools/pod.py apply {name}
"""
HEAD_NAMES = """# LOTE {name} · MODO NOMBRES · {n} elementos
# Lee tools/TRADUCIR_LOTE.md (sección «Modo NOMBRES»). Casi todos los nombres se quedan igual.
# Salida: crea work_queue/out/{name}.txt SOLO con los que tengan forma española habitual:  <número> = <nombre en español>
#         (si no cambias ninguno, escribe una única línea:  # sin cambios)
# Luego ejecuta:  python tools/pod.py apply {name}
"""
HEAD_REVIEW = """# LOTE {name} · MODO REVISAR ({rule}) · {n} elementos
# Lee tools/TRADUCIR_LOTE.md si no lo has leído. Corrige la traducción ES solo si hace falta.
# Salida: crea work_queue/out/{name}.txt SOLO con las líneas que cambies:  <número> = <traducción corregida>
#         (si no cambias nada, escribe una única línea:  # sin cambios)
# Luego ejecuta:  python tools/pod.py apply {name}
"""


def write_batch(name, mode, items, gloss, rule=""):
    """items: lista de dicts {en, targets, key, rel, prev_en?, prev_es?, es?, why?}"""
    for d in ("todo", "index", "out", "done"):
        (Q / d).mkdir(parents=True, exist_ok=True)
    head = {"pending": HEAD_PENDING, "review": HEAD_REVIEW, "names": HEAD_NAMES}[mode].format(name=name, n=len(items), rule=rule)
    g = glossary_for([i["en"] for i in items], gloss) if mode != "names" else []
    body = [head]
    if g:
        body.append("# GLOSARIO OBLIGATORIO (inglés = español):")
        for r in g:
            body.append(f"#   {r['en']} = {r['es']}" + (f"   ({r['note']})" if r["note"] else ""))
    index = {}
    cur = None
    for n, it in enumerate(items, 1):
        if it["rel"] != cur:
            cur = it["rel"]
            body.append(f"\n## archivo: {cur}")
        if mode == "names":
            body.append(f"{n}: {it['en']}")
            index[str(n)] = {"en": it["en"], "expect": it["en"], "targets": it["targets"], "tries": it.get("tries", 0)}
            continue
        body.append(f"\n{n} | clave: {it['key']}" + (f"  (+{len(it['targets']) - 1} iguales)" if len(it["targets"]) > 1 else ""))
        if it.get("why"):
            body.append(f"MOTIVO: {it['why']}")
        if it.get("prev_en"):
            body.append(f"EN-ANTIGUO: {it['prev_en']}")
            body.append(f"ES-ANTIGUO: {it['prev_es']}")
        body.append(f"EN: {it['en']}")
        if mode == "review":
            body.append(f"ES: {it['es']}")
        index[str(n)] = {"en": it["en"], "expect": it["es"] if mode != "pending" else it["en"],
                         "targets": it["targets"], "tries": it.get("tries", 0)}
    (Q / "todo" / f"{name}.txt").write_text("\n".join(body) + "\n", encoding="utf-8")
    (Q / "index" / f"{name}.json").write_text(json.dumps({"mode": mode, "items": index}, ensure_ascii=False, indent=1), encoding="utf-8")


def chunk(items, max_items=None):
    max_items = max_items or CFG["batch_max_items"]
    out, cur, size = [], [], 0
    for it in items:
        c = len(it["en"]) + len(it.get("es", "")) + len(it.get("prev_es", ""))
        if cur and (len(cur) >= max_items or size + c > CFG["batch_max_chars"]):
            out.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += c
    if cur:
        out.append(cur)
    return out


def cmd_batch(a):
    with QueueLock():
        _batch(a)


def _batch(a):
    files = [a.files] if a.files else None
    gloss = load_glossary()
    if a.mode == "names":
        busy = queued_ids()
        groups = {}
        for rel in en_files():
            if not match_any(rel, CFG["names_files"]):
                continue
            en, es = load_pair(rel)
            idx = es.index() if es else {}
            for l in en.kvs():
                e = idx.get((l["key"], l["occ"]))
                if not e or e["value"] != l["value"] or not translatable(l["value"]) or (rel, l["key"], l["occ"]) in busy:
                    continue
                g = groups.setdefault(l["value"], {"rel": rel, "key": l["key"], "en": l["value"], "es": l["value"], "targets": []})
                g["targets"].append([rel, l["key"], l["occ"]])
        items = list(groups.values())
    elif a.mode == "review":
        items = [dict(it, targets=[[it["rel"], it["key"], it["occ"]]]) for it in check_items(files, a.rule)]
        items = [i for i in items if tuple(i["targets"][0]) not in queued_ids()]
    else:
        pend = list(pending_items(files))
        if a.scope == "update":
            lf = Q / "last_sync.json"
            if not lf.exists():
                sys.exit("No hay registro de actualización (work_queue/last_sync.json): ejecuta antes 'sync'.")
            last = json.loads(lf.read_text(encoding="utf-8"))
            newf = set(last["new_files"])
            ks = {(rel, k, o) for rel, lst in last["keys"].items() for k, o in lst}
            pend = [p for p in pend if p[0] in newf or (p[0], p[1], p[2]) in ks]
        busy = queued_ids()
        pend = [p for p in pend if (p[0], p[1], p[2]) not in busy]
        if not a.no_tm:
            tm = build_tm()
            assign = {(r, k, o): (v, tm[v]) for r, k, o, v in pend if v in tm}
            if assign:
                touched, _ = write_values(assign)
                print(f"Memoria de traducción: {len(assign)} claves rellenadas sin IA")
                flip_headers(touched)
                pend = [p for p in pend if (p[0], p[1], p[2]) not in assign]
        changed = json.loads((Q / "changed.json").read_text(encoding="utf-8")) if (Q / "changed.json").exists() else {}
        groups = {}
        for rel, key, occ, v in sorted(pend, key=lambda p: batch_order(p[0])):
            if v in groups:
                groups[v]["targets"].append([rel, key, occ])
                continue
            it = {"rel": rel, "key": key, "en": v, "targets": [[rel, key, occ]]}
            c = changed.get(rel, {}).get(key)
            if c:
                it["prev_en"], it["prev_es"] = c["old_en"], c["old_es"]
            groups[v] = it
        items = list(groups.values())
    if a.limit:
        items = items[: a.limit * CFG["batch_max_items"]]
    chunks = chunk(items, CFG["names_batch_max_items"] if a.mode == "names" else None)
    if a.limit:
        chunks = chunks[: a.limit]
    prefix = PREFIX["update" if a.scope == "update" and a.mode == "pending" else a.mode]
    for ch in chunks:
        name = next_batch_name(prefix)
        write_batch(name, a.mode, ch, gloss, a.rule or "")
    n = sum(len(c) for c in chunks)
    if chunks and a.mode == "pending":
        tiers = Counter(splat_of(it["rel"])[1] for ch in chunks for it in ch)
        print("Línea de juego: " + " · ".join(f"{k} {v}" for k, v in tiers.most_common()))
    names = [p.stem for p in sorted((Q / "todo").glob(f"{prefix}*.txt"))]
    print(f"{len(chunks)} lotes creados ({n} textos únicos) en work_queue/todo"
          + (f" · lotes {prefix} en cola: {names[0]}…{names[-1]}" if names else ""))
    if chunks:
        print(f"Siguiente paso: python tools/pod.py next --prefix {prefix}")


def cmd_next(a):
    todo = sorted((Q / "todo").glob(f"{a.prefix or ''}*.txt")) if (Q / "todo").exists() else []
    if not todo:
        print("NO QUEDAN LOTES" + (f" CON PREFIJO {a.prefix}" if a.prefix else ""))
        return
    p = todo[0]
    print(f"SIGUIENTE: {p.relative_to(ROOT).as_posix()}  (quedan {len(todo)})")
    if a.show:
        print(p.read_text(encoding="utf-8"))


OUT_RE = re.compile(r"^\s*(\d+)\s*=\s?(.*)$")


class QueueLock:
    """Bloqueo entre procesos para que varios agentes puedan aplicar a la vez."""

    def __enter__(self):
        import os, time
        Q.mkdir(exist_ok=True)
        self.p = Q / ".lock"
        for _ in range(600):
            try:
                self.fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                if time.time() - self.p.stat().st_mtime > 300:
                    self.p.unlink(missing_ok=True)
                time.sleep(0.5)
        sys.exit("No se pudo obtener el bloqueo de work_queue/.lock")

    def __exit__(self, *exc):
        import os
        os.close(self.fd)
        self.p.unlink(missing_ok=True)


def cmd_apply(a):
    with QueueLock():
        _apply(a)


def _apply(a):
    names = a.names
    if a.all:
        names = sorted(p.stem for p in (Q / "out").glob("*.txt"))
    gloss = load_glossary()
    for name in names:
        idxf = Q / "index" / f"{name}.json"
        outf = Q / "out" / f"{name}.txt"
        if not idxf.exists() or not outf.exists():
            print(f"{name}: falta el índice o la salida ({outf.relative_to(ROOT).as_posix()})")
            continue
        meta = json.loads(idxf.read_text(encoding="utf-8"))
        items = meta["items"]
        got = {}
        for line in outf.read_text(encoding="utf-8-sig").splitlines():
            m = OUT_RE.match(line)
            if m:
                got[m.group(1)] = m.group(2)
        assign, keep, bad = {}, [], []
        for n, it in items.items():
            if n not in got:
                if meta["mode"] == "pending":
                    bad.append((n, it, "falta la línea de este número en la salida"))
                continue
            es, errs = validate(it["en"], got[n])
            if errs:
                bad.append((n, it, "; ".join(errs), got[n]))
                continue
            for t in it["targets"]:
                assign[tuple(t)] = (it["expect"], es)
            if meta["mode"] == "pending" and es == it["en"]:
                keep.extend(t[1] for t in it["targets"])
        touched, stale = write_values(assign, keep)
        flip_headers(touched)
        if assign:
            log_applied(name, assign.keys())
        print(f"{name}: {len(assign)} claves escritas, {len(bad)} rechazadas, {stale} ya no coincidían (omitidas)")
        for d in ("done",):
            shutil.move(str(Q / "todo" / f"{name}.txt"), Q / d / f"{name}.txt") if (Q / "todo" / f"{name}.txt").exists() else None
            shutil.move(str(outf), Q / d / f"{name}.out.txt")
            shutil.move(str(idxf), Q / d / f"{name}.json")
        if bad:
            retry, manual = [], []
            for b in bad:
                n, it, why = b[0], b[1], b[2]
                t0 = it["targets"][0]
                rec = {"rel": t0[0], "key": t0[1], "en": it["en"], "es": it["expect"], "targets": it["targets"],
                       "tries": it["tries"] + 1,
                       "why": f"RECHAZADO ({why})" + (f" · tu texto fue: {b[3]}" if len(b) > 3 else "")}
                (manual if rec["tries"] >= CFG["max_tries"] else retry).append(rec)
                print(f"   ✘ {n} {t0[1]}: {why}")
            if retry:
                rn = next_batch_name(name[0])
                write_batch(rn, meta["mode"], retry, gloss, "reintento")
                print(f"   → reintento en lote {rn}")
            if manual:
                (Q / "manual").mkdir(exist_ok=True)
                mf = Q / "manual" / f"{name}.json"
                mf.write_text(json.dumps(manual, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"   → {len(manual)} para revisión manual en {mf.relative_to(ROOT).as_posix()}")


# ---------------------------------------------------------------- check / revisión

def check_items(files=None, only=None, keys=None):
    """keys = conjunto de (rel, clave, ocurrencia) al que limitarse (p. ej. lo que acaba de escribir el agente)."""
    full = load_glossary()
    gloss = [g for g in full if "l" in g["flags"]]
    keep_display = {g["en"].lower() for g in full if g["en"].lower() == g["es"].lower()} | {k.lower() for k in CFG["keep_display"]}
    customs = vanilla_es_customs()
    keep = load_keep()
    rels = sorted({k[0] for k in keys}) if keys is not None else en_files()
    for rel in rels:
        if files and not match_any(rel, files):
            continue
        en, es = load_pair(rel)
        if not es or (keys is None and es.header != "l_spanish"):
            continue
        idx = es.index()
        for l in en.kvs():
            e = idx.get((l["key"], l["occ"]))
            if keys is not None and (rel, l["key"], l["occ"]) not in keys:
                continue
            if not e:
                if keys is not None:
                    yield {"rel": rel, "key": l["key"], "occ": l["occ"], "en": l["value"], "es": "", "why": "clave ausente en español"}
                continue
            if e["value"] == l["value"]:
                if keys is not None and translatable(l["value"]) and l["key"] not in keep:
                    yield {"rel": rel, "key": l["key"], "occ": l["occ"], "en": l["value"], "es": e["value"], "why": "sigue sin traducir"}
                continue
            ev, sv = l["value"], e["value"]
            why = []
            if only in (None, "tokens"):
                d = token_diff(ev, sv)
                if d:
                    why.append(d.replace("|", "·"))
            if only in (None, "custom"):
                bad = [m.group(0) for m in ES_CUSTOM_RE.finditer(sv) if m.group(1) or m.group(2) not in customs]
                if bad:
                    why.append("Custom inexistente: " + ",".join(bad))
            if only in (None, "spaces") and ("  " in sv and "  " not in ev or re.search(r"\s[,.;:](?!\.)", strip_markup(sv, "X")) and not re.search(r"\s[,.;:]", strip_markup(ev, "X"))):
                why.append("espacios sobrantes")
            if only in (None, "punct"):
                plain = strip_markup(sv)
                if plain.count("?") > plain.count("¿") or plain.count("!") > plain.count("¡"):
                    why.append("falta ¿ o ¡")
                elif plain.count("¡") > strip_markup(ev).count("!"):
                    why.append("¡ que no está en el inglés (¿confusión con el cierre #!?)")
            if only in (None, "glossary"):
                pe, ps = strip_markup(ev), strip_markup(sv).lower()
                for g in gloss:
                    if g["re"].search(pe) and g["es"].lower() not in ps:
                        why.append(f"glosario: {g['en']} → {g['es']}")
                        break
            if only in (None, "display"):
                same = [d for d in display_args(sv) if d in display_args(ev) and translatable(d) and d.lower() not in keep_display]
                if same:
                    why.append("texto de Glossary/Concept sin traducir: " + ", ".join(sorted(set(same))))
            if only in (None, "english"):
                ps = strip_markup(sv)
                for w in CFG["english_leftovers"]:
                    if re.search(r"(?<![\w'])" + re.escape(w) + r"(?![\w'])", ps):
                        why.append(f"palabra inglesa: {w}")
                        break
            if why:
                yield {"rel": rel, "key": l["key"], "occ": l["occ"], "en": ev, "es": sv, "why": "; ".join(why)}


APPLIED_LOG = "applied.jsonl"


def log_applied(name, keys):
    """Registro append-only de lo aplicado, con marca de tiempo (lo usa 'verify')."""
    import time
    with open(Q / APPLIED_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.time(), "batch": name, "keys": sorted(keys)}, ensure_ascii=False) + "\n")


def applied_keys(all_=False):
    """Claves escritas por lotes ya aplicados. Por defecto, solo las nuevas desde la última verificación."""
    marker = Q / ".verified"
    since = 0.0
    if marker.exists() and not all_:
        try:
            since = float(marker.read_text(encoding="utf-8").strip() or 0)
        except ValueError:
            since = marker.stat().st_mtime
    keys, lotes = set(), []
    log = Q / APPLIED_LOG
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec["at"] <= since:
                continue
            lotes.append(rec["batch"])
            keys.update(tuple(k) for k in rec["keys"])
    else:  # compatibilidad con lotes aplicados antes de existir el registro
        for f in sorted((Q / "done").glob("*.json")):
            if f.stat().st_mtime <= since:
                continue
            lotes.append(f.stem)
            for it in json.loads(f.read_text(encoding="utf-8"))["items"].values():
                keys.update(tuple(t) for t in it["targets"])
    return keys, sorted(set(lotes))


def cmd_verify(a):
    keys, lotes = applied_keys(a.all)
    if not keys:
        print("Nada nuevo que verificar (usa --all para revisar todo lo aplicado).")
        return
    probs = list(check_items([a.files] if a.files else None, None, keys))
    print(f"Verificando {len(keys)} claves de {len(lotes)} lotes ({lotes[0]}…{lotes[-1]}): {len(probs)} con avisos")
    cnt = Counter()
    for p in probs:
        cnt[p["why"].split(":")[0]] += 1
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")
    for p in probs[:20]:
        print(f"   · {p['rel']} · {p['key']}: {p['why']}")
        print(f"     EN: {p['en'][:140]}")
        print(f"     ES: {p['es'][:140]}")
    if probs and a.batch:
        gloss = load_glossary()
        items = [dict(p, targets=[[p["rel"], p["key"], p["occ"]]]) for p in probs if p["es"]]
        items = [i for i in items if tuple(i["targets"][0]) not in queued_ids()]
        for ch in chunk(items):
            write_batch(next_batch_name("R"), "review", ch, gloss, "verificación")
        print(f"→ lotes de corrección creados: python tools/pod.py next --prefix R")
    import time
    (Q / ".verified").write_text(str(time.time()), encoding="utf-8")


def cmd_check(a):
    files = [a.files] if a.files else None
    cnt = Counter()
    ex = defaultdict(list)
    for it in check_items(files, a.rule):
        for w in it["why"].split("; "):
            k = w.split(":")[0]
            cnt[k] += 1
            if len(ex[k]) < a.examples:
                ex[k].append(f"{it['rel']} · {it['key']}\n      EN: {it['en'][:150]}\n      ES: {it['es'][:150]}\n      ({w})")
    for k, v in cnt.most_common():
        print(f"== {k}: {v}")
        for e in ex[k]:
            print("   " + e)


# ---------------------------------------------------------------- build

def cmd_build(a):
    pub = ROOT / CFG["publish_dir"]
    stats = Counter()
    wanted = set()
    for rel in en_files():
        dst = pub / es_rel(rel)
        wanted.add(dst.resolve())
        src = ES_DIR / es_rel(rel)
        es = Loc(src) if src.exists() else None
        if es and es.header == "l_spanish":
            en_idx = Loc(EN_DIR / rel).index()
            data = es.text()
            missing = [k for k in en_idx if k not in es.index()]
            if missing:
                stats["claves que faltaban (rellenas con inglés)"] += len(missing)
                es_lines = es.lines + [{"raw": en_idx[k]["raw"], "kind": "other"} for k in missing]
                es.lines = es_lines
                data = es.text()
            stats["traducidos"] += 1
        else:
            en = Loc(EN_DIR / rel)
            en.set_header("l_spanish")
            data = en.text()
            stats["en inglés (pendientes)"] += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.read_bytes() != data.encode("utf-8"):
            dst.write_bytes(data.encode("utf-8"))
            stats["archivos escritos"] += 1
    for p in pub.rglob("*.yml"):
        if p.resolve() not in wanted:
            stats["sobrantes borrados"] += 1
            p.unlink()
    desc = ROOT / CFG["publish_descriptor"]
    d = desc.read_text(encoding="utf-8")
    if a.version:
        d = re.sub(r'^version="[^"]*"', f'version="{a.version}"', d, flags=re.M)
    base = base_mod_info() if a.sync_supported else None
    if a.sync_supported:
        if base:
            d = re.sub(r'supported_version="[^"]*"', f'supported_version="{base["supported"]}"', d)
            update_readme_base_version(base)
        else:
            print(f"AVISO: no encuentro {CFG['workshop_descriptor']}; supported_version y README sin cambiar")
    desc.write_bytes(d.encode("utf-8"))  # LF, como lo escribe el launcher (ver .gitattributes)
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(re.sub(r"\n\s*", " · ", d.strip()))
    if base:
        print(f"Mod base: {base_version_text(base)}")


def base_mod_info():
    """Versión del Princes of Darkness instalado desde el Workshop: descriptor y registro de cambios."""
    wp = Path(CFG["workshop_descriptor"])
    if not wp.exists():
        return None
    t = wp.read_text(encoding="utf-8", errors="replace")
    info = {"version": re.search(r'^version="([^"]*)"', t, re.M).group(1),
            "supported": re.search(r'supported_version="([^"]*)"', t).group(1), "name": "", "date": ""}
    log = wp.parent / CFG.get("base_changelog", "POD_change_log.info")
    if log.exists():
        # primera cabecera: # Princes of Darkness, "Descent of the Dragons", Version 1.19.0.6, 6/24/2026
        m = re.search(r'^#\s*[^,\n]*,\s*"([^"]+)",\s*Version\s+([\w.]+),\s*([\d/]+)', log.read_text(encoding="utf-8", errors="replace"), re.M)
        if m and m.group(2) == info["version"]:
            info["name"], info["date"] = m.group(1), m.group(3)
    return info


def base_version_text(b):
    return b["version"] + (f" «{b['name']}»" if b["name"] else "")


def update_readme_base_version(b):
    """Actualiza en README.md el texto entre <!-- base-version --> y <!-- /base-version -->."""
    p = ROOT / "README.md"
    if not p.exists():
        return
    s = p.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- base-version -->).*?(<!-- /base-version -->)", lambda m: m.group(1) + base_version_text(b) + m.group(2), s)
    if new != s:
        p.write_text(new, encoding="utf-8")
        print(f"README: versión del mod base → {base_version_text(b)}")



FIXES = [
    ("GetCustom('ES_O') → Custom('ES_OA')", re.compile(r"\.GetCustom\('ES_O'\)"), ".Custom('ES_OA')"),
    ("flag con espacio '| E]'", re.compile(r"\|\s+([A-Za-z]+)\]"), r"|\1]"),
    ("espacio en \"Concept ('\"", re.compile(r"\[(\w+) +\('"), r"[\1('"),
]


def dirty_rels():
    """Archivos de spanish/ modificados respecto a HEAD, en claves de inglés."""
    out = git("status", "--porcelain", "--", CFG["es_dir"]).stdout.splitlines()
    rels = set()
    for line in out:
        p = line[3:].strip().strip('"').split(" -> ")[-1]
        if p.startswith(CFG["es_dir"] + "/"):
            rels.add(p[len(CFG["es_dir"]) + 1:].replace("l_spanish", "l_english"))
    return rels


def cmd_fix(a):
    with QueueLock():
        _fix(a)


def _fix(a):
    cnt = Counter()
    only = dirty_rels() if a.dirty else None
    if a.dirty:
        print(f"Solo archivos modificados: {len(only)}")
    for rel in en_files():
        if only is not None and rel not in only:
            continue
        if a.files and not match_any(rel, [a.files]):
            continue
        en, es = load_pair(rel)
        if not es:
            continue
        idx, dirty = es.index(), False
        for l in en.kvs():
            e = idx.get((l["key"], l["occ"]))
            if not e:
                continue
            if e["unclosed"] and not l["unclosed"]:
                # falta la comilla de cierre: en el juego se traga la línea siguiente
                es.set_value(e, e["value"].rstrip())
                cnt["comilla de cierre que faltaba"] += 1
                dirty = True
            if e["value"] == l["value"]:
                continue
            v = e["value"]
            for name, rx, rep in FIXES:
                v, n = rx.subn(rep, v)
                cnt[name] += n
            if "  " not in l["value"]:
                v, n = re.subn(r"(?<=\S) {2,}(?=\S)", " ", v)
                cnt["dobles espacios"] += n
            if v != e["value"]:
                es.set_value(e, v)
                dirty = True
        if dirty and not a.dry_run:
            es.save()
    for k, v in cnt.items():
        print(f"{k}: {v}{'  (simulación)' if a.dry_run else ''}")


RULES = ["tokens", "custom", "spaces", "punct", "glossary", "display", "english"]

# ---------------------------------------------------------------- lotes que fallan enteros

def cmd_setaside(a):
    """Aparta un lote que el agente no ha podido procesar: lo divide en dos o, si es de un solo texto, va a manual/."""
    with QueueLock():
        idxf = Q / "index" / f"{a.name}.json"
        if not idxf.exists():
            sys.exit(f"No existe el lote {a.name} en la cola.")
        meta = json.loads(idxf.read_text(encoding="utf-8"))
        items = []
        for it in meta["items"].values():
            rel, key, _ = it["targets"][0]
            items.append({"rel": rel, "key": key, "en": it["en"], "es": it["expect"], "targets": it["targets"],
                          "tries": it.get("tries", 0), "why": f"LOTE APARTADO ({a.reason})"})
        if a.split and len(items) > 1:
            half = (len(items) + 1) // 2
            gloss = load_glossary()
            names = []
            for part in (items[:half], items[half:]):
                n = next_batch_name(a.name[0])
                write_batch(n, meta["mode"], [dict(i, why="") for i in part], gloss, "dividido")
                names.append(n)
            print(f"{a.name}: dividido en {names[0]} y {names[1]} ({a.reason})")
        else:
            (Q / "manual").mkdir(exist_ok=True)
            mf = Q / "manual" / f"{a.name}.json"
            prev = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else []
            mf.write_text(json.dumps(prev + items, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{a.name}: {len(items)} textos a work_queue/manual/ ({a.reason})")
        for p in (Q / "todo" / f"{a.name}.txt", idxf, Q / "out" / f"{a.name}.txt"):
            if p.exists():
                p.unlink()

# ---------------------------------------------------------------- limpieza de la cola

def cmd_clean(a):
    """Limpia work_queue sin tocar trabajo pendiente: solo borra lo resuelto, lo huérfano o lo antiguo ya verificado."""
    import time
    with QueueLock():
        _clean(a, time.time())


def _clean(a, now):
    dry = a.dry_run
    cfg = CFG.get("clean", {})
    keep_done = cfg.get("keep_done_days", 7) * 86400
    keep_log = cfg.get("keep_log_days", 60) * 86400
    cnt = Counter()
    cache = {}

    def current(rel, key, occ):
        """(valor español, valor inglés) actuales de una clave; None si no existe."""
        if rel not in cache:
            cache[rel] = load_pair(rel) if (EN_DIR / rel).exists() else (None, None)
        en, es = cache[rel]
        e = es.index().get((key, occ)) if es else None
        l = en.index().get((key, occ)) if en else None
        return (e["value"] if e else None), (l["value"] if l else None)

    def resolved(targets, expect):
        """Ya no hace falta: la clave cambió desde que se registró, o ya no existe en inglés."""
        for rel, key, occ in targets:
            es_v, en_v = current(rel, key, occ)
            if en_v is not None and es_v == expect:
                return False
        return True

    def rm(p):
        if p.exists():
            cnt["archivos borrados"] += 1
            if not dry:
                p.unlink()

    # 1. manual/: quitar lo que ya se corrigió; con --requeue, devolver el resto a la cola
    requeue = []
    for f in sorted((Q / "manual").glob("*.json")) if (Q / "manual").exists() else []:
        items = json.loads(f.read_text(encoding="utf-8"))
        left = [it for it in items if not resolved(it["targets"], it["es"])]
        cnt["manual: resueltos quitados"] += len(items) - len(left)
        if a.requeue:
            requeue.extend(left)
            left = []
        if not left:
            rm(f)
        elif len(left) < len(items) and not dry:
            f.write_text(json.dumps(left, ensure_ascii=False, indent=1), encoding="utf-8")
        cnt["manual: sin resolver"] += len(left)
    if requeue:
        gloss = load_glossary()
        for mode in ("pending", "review"):
            its = [dict(it, tries=0) for it in requeue if (it["es"] == it["en"]) == (mode == "pending")]
            for ch in chunk(its):
                cnt["manual: devueltos a la cola (M)"] += len(ch)
                if not dry:
                    write_batch(next_batch_name("M"), mode, ch, gloss, "manual")

    # 2. todo/ index/ out/: lotes obsoletos (todo su contenido ya cambió) y archivos huérfanos
    todo, index, out = (Q / "todo"), (Q / "index"), (Q / "out")
    names = {p.stem for d in (todo, index) if d.exists() for p in d.glob("*.*")}
    names |= {p.stem for p in out.glob("*.txt")} if out.exists() else set()
    for n in sorted(names):
        t, i, o = todo / f"{n}.txt", index / f"{n}.json", out / f"{n}.txt"
        if not i.exists():
            if t.exists() or o.exists():
                cnt["lotes huérfanos (sin índice)"] += 1
                rm(t); rm(o)
            continue
        if not t.exists() and not o.exists():
            cnt["índices huérfanos"] += 1
            rm(i)
            continue
        items = json.loads(i.read_text(encoding="utf-8"))["items"].values()
        if not o.exists() and all(resolved(it["targets"], it["expect"]) for it in items):
            cnt["lotes obsoletos (ya resueltos por otra vía)"] += 1
            rm(t); rm(i)

    # 3. done/: lotes aplicados, ya verificados y más antiguos que keep_done_days
    marker = Q / ".verified"
    try:
        verified = float(marker.read_text(encoding="utf-8").strip() or 0) if marker.exists() else 0.0
    except ValueError:
        verified = marker.stat().st_mtime
    log = Q / APPLIED_LOG
    records = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.exists() else []
    applied_at = {}
    for r in records:
        applied_at[r["batch"]] = max(applied_at.get(r["batch"], 0), r["at"])
    for p in sorted((Q / "done").glob("*")) if (Q / "done").exists() else []:
        name = p.name.split(".")[0]
        at = applied_at.get(name, p.stat().st_mtime)
        if at <= verified and now - at > keep_done:
            rm(p)

    # 4. applied.jsonl: registros ya verificados y más antiguos que keep_log_days
    keep = [r for r in records if r["at"] > verified or now - r["at"] <= keep_log]
    if len(keep) < len(records):
        cnt["registros de applied.jsonl quitados"] += len(records) - len(keep)
        if not dry:
            log.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")

    # 5. changed.json y last_sync.json: solo lo que sigue pendiente
    pend = {(r, k, o) for r, k, o, _ in pending_items()}
    f = Q / "changed.json"
    if f.exists():
        ch = json.loads(f.read_text(encoding="utf-8"))
        new = {rel: {k: v for k, v in d.items() if (rel, k, 0) in pend} for rel, d in ch.items()}
        new = {rel: d for rel, d in new.items() if d}
        cnt["changed.json: entradas quitadas"] += sum(map(len, ch.values())) - sum(map(len, new.values()))
        if new != ch and not dry:
            f.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    f = Q / "last_sync.json"
    if f.exists():
        ls = json.loads(f.read_text(encoding="utf-8"))
        pend_files = {r for r, _, _ in pend}
        keys = {rel: [k for k in v if (rel, k[0], k[1]) in pend] for rel, v in ls["keys"].items()}
        keys = {rel: v for rel, v in keys.items() if v}
        new = dict(ls, keys=keys, new_files=[r for r in ls["new_files"] if r in pend_files])
        cnt["last_sync.json: claves quitadas"] += sum(map(len, ls["keys"].values())) - sum(map(len, keys.values()))
        if new != ls and not dry:
            f.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    removed = list((Q / "removed").rglob("*.yml")) if (Q / "removed").exists() else []
    tag = "  (simulación)" if dry else ""
    for k, v in cnt.items():
        if v:
            print(f"{k}: {v}{tag}")
    if not any(cnt.values()):
        print("Nada que limpiar.")
    if cnt["manual: sin resolver"]:
        print(f"→ {cnt['manual: sin resolver']} textos siguen en work_queue/manual/: corrígelos a mano o "
              f"devuélvelos a la cola con 'clean --requeue' para que los traduzca otro agente.")
    if removed:
        print(f"→ {len(removed)} archivos en work_queue/removed/ (ya no existen en inglés): revísalos y bórralos a mano.")

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("status"); s.add_argument("--top", type=int, default=25)
    s = sp.add_parser("sync"); s.add_argument("--base"); s.add_argument("--dry-run", action="store_true"); s.add_argument("--prune", action="store_true")
    s = sp.add_parser("batch"); s.add_argument("--mode", choices=["pending", "review", "names"], default="pending")
    s.add_argument("--rule", choices=RULES)
    s.add_argument("--files"); s.add_argument("--limit", type=int); s.add_argument("--no-tm", action="store_true")
    s.add_argument("--scope", choices=["all", "update"], default="all", help="update = solo lo que trajo el último sync")
    s = sp.add_parser("next"); s.add_argument("--show", action="store_true"); s.add_argument("--prefix", choices=list(PREFIXES))
    s = sp.add_parser("apply"); s.add_argument("names", nargs="*"); s.add_argument("--all", action="store_true")
    s = sp.add_parser("check"); s.add_argument("--files"); s.add_argument("--rule", choices=RULES); s.add_argument("--examples", type=int, default=3)
    s = sp.add_parser("build"); s.add_argument("--version"); s.add_argument("--sync-supported", action="store_true")
    sp.add_parser("glossary")
    s = sp.add_parser("fix"); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--dirty", action="store_true", help="solo los archivos de spanish/ modificados respecto a HEAD")
    s.add_argument("--files", help="patrón, p. ej. \"traits/*\"")
    s = sp.add_parser("verify"); s.add_argument("--all", action="store_true"); s.add_argument("--batch", action="store_true")
    s.add_argument("--files")
    s = sp.add_parser("setaside"); s.add_argument("name"); s.add_argument("--reason", default="fallo del agente")
    s.add_argument("--split", action="store_true", help="dividir en dos lotes en vez de mandarlo a manual/")
    s = sp.add_parser("clean"); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--requeue", action="store_true", help="devuelve a la cola lo que siga en manual/")
    a = ap.parse_args()
    {"status": cmd_status, "sync": cmd_sync, "batch": cmd_batch, "next": cmd_next, "apply": cmd_apply,
     "check": cmd_check, "build": cmd_build, "glossary": cmd_glossary, "fix": cmd_fix,
     "verify": cmd_verify, "clean": cmd_clean, "setaside": cmd_setaside}[a.cmd](a)


if __name__ == "__main__":
    main()
