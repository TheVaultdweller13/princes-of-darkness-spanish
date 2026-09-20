#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera tools/glossary_books.tsv a a partir de los glosarios oficiales en PDF en docs/".

Necesita `pdftotext` (poppler) en el PATH. Se ejecuta solo cuando se añade o cambia un PDF:

    python tools/extract_glossaries.py [--all] [--min-count 1]

De cada PDF toma la lista «inglés - español» y se queda con los términos que de verdad
aparecen en english/, para no llenar las cabeceras de los lotes de ruido. Por defecto
descarta las palabras sueltas que no sean propias del mundo de juego: un término de una
sola palabra solo entra si en el inglés del mod aparece en mayúscula a mitad de frase
(Garou, Wyrm…) y además es raro en la localización inglesa del CK3, que sirve de muestra
de lenguaje corriente (así se descartan Power, Court, Realm…). Con --all entran todos.

El archivo generado es el de menor prioridad: glossary_mod.tsv y glossary.tsv lo pisan.
"""
import argparse
import collections
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pod  # noqa: E402

ROOT = pod.ROOT
PAIR_RE = re.compile(r"^\s{0,6}([^\s].{0,60}?)\s+-\s+(\S.{0,70})\s*$")
EN_OK_RE = re.compile(r"^[A-Za-z0-9'’\-\.,\(\) ]+$")
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ']+")
# Palabras corrientes: como término suelto no aportan y ensucian las cabeceras.
COMUNES = set("""the a an of and or in on to for with will one first time area master set point head trait
lore matter see you your they this that from good bad great small change search night child divine favor
gathering gather physical skills demon ancient wrath corruption despair hungry necromancer seeking""".split())
MAX_EN_VANILLA = 20  # apariciones en el CK3 inglés a partir de las cuales una palabra suelta es corriente


def frecuencia_vanilla():
    """Cuántas veces aparece cada palabra en la localización inglesa del CK3 (lenguaje corriente)."""
    d = Path(pod.CFG["vanilla_custom_loc"]).parent.parent / "localization" / "english"
    cuenta = collections.Counter()
    if d.is_dir():
        for f in d.rglob("*.yml"):
            cuenta.update(w.lower() for w in WORD_RE.findall(f.read_text(encoding="utf-8-sig", errors="replace")))
    return cuenta


def texto_pdf(pdf):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "g.txt"
        subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), str(out)], check=True)
        return out.read_text(encoding="utf-8")


def pares(texto):
    """Pares «inglés - español» de la lista del glosario."""
    for linea in texto.splitlines():
        m = PAIR_RE.match(linea.rstrip())
        if not m:
            continue
        en, es = m.group(1).strip(), m.group(2).strip()
        if len(en) < 4 or len(es) < 2 or not EN_OK_RE.match(en) or re.search(r"\d{2,}", en + es):
            continue
        es = re.split(r"\s{3,}", es)[0].strip()  # la extracción a veces pega la columna siguiente
        if es:
            yield en, es


def corpus_ingles():
    """(texto completo, nombres propios) del inglés del mod."""
    textos = []
    for rel in pod.en_files():
        loc = pod.Loc(pod.EN_DIR / rel)
        textos.extend(pod.strip_markup(l["value"]) for l in loc.kvs())
    propios = set()
    for t in textos:
        palabras = WORD_RE.findall(t)
        for i, w in enumerate(palabras[1:], 1):  # a mitad de frase, no tras punto
            if w[:1].isupper() and not palabras[i - 1].endswith((".", ":", "!", "?")):
                propios.add(w.lower())
    return textos, propios


def ngramas(texto, maxn=5):
    ws = WORD_RE.findall(texto)
    for i in range(len(ws)):
        for n in range(1, maxn + 1):
            if i + n <= len(ws):
                yield " ".join(ws[i:i + n]).lower()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="incluir también las palabras sueltas corrientes")
    ap.add_argument("--min-count", type=int, default=1, help="apariciones mínimas en el mod")
    a = ap.parse_args()

    libros = {}
    for pdf in sorted(ROOT.glob("**/Glosario *.pdf")):
        fuente = pdf.stem.replace("Glosario ", "").replace(" Ampliado", "").replace(" Básico", "")
        n = 0
        for en, es in pares(texto_pdf(pdf)):
            if libros.setdefault(en.lower(), (en, es, fuente))[2] == fuente:
                n += 1
        print(f"{pdf.name}: {n} términos")

    # Lo que ya está en los glosarios de mayor prioridad (no el generado, o no quedaría nada al regenerar).
    ya = set()
    for f in ("glossary.tsv", "glossary_mod.tsv"):
        p = pod.TOOLS / f
        if p.exists():
            ya.update(l.split("\t")[0].strip().lower() for l in p.read_text(encoding="utf-8").splitlines()
                      if l.strip() and not l.startswith("#") and "\t" in l)
    vanilla = frecuencia_vanilla()
    if not vanilla:
        print("AVISO: no encuentro la localización inglesa del CK3; no puedo filtrar palabras corrientes.")
    textos, propios = corpus_ingles()
    usos = collections.Counter()
    for t in textos:
        for g in set(ngramas(t)):
            if g in libros:
                usos[g] += 1

    filas = []
    for g, veces in usos.items():
        en, es, fuente = libros[g]
        if veces < a.min_count:
            continue
        if en.lower() in ya:
            continue
        if " " not in en and not a.all:
            if en.lower() in COMUNES or en.lower() not in propios or en.lower() == es.lower():
                continue
            if vanilla.get(en.lower(), 0) > MAX_EN_VANILLA:
                continue
        filas.append((en, es, fuente, veces))
    filas.sort(key=lambda f: (-f[3], f[0].lower()))

    salida = [f"# GENERADO por 'python tools/extract_glossaries.py' desde los glosarios oficiales en PDF.",
              "# No editar a mano: lo que haya que corregir o fijar va en glossary.tsv, que tiene prioridad.",
              "# Columnas: inglés\tespañol\tmarcas (b = glosario oficial de un libro)\tlibro\tusos en el mod"]
    for en, es, fuente, veces in filas:
        salida.append(f"{en}\t{es}\tb\t{fuente}\t{veces}")
    (pod.TOOLS / "glossary_books.tsv").write_text("\n".join(salida) + "\n", encoding="utf-8")
    print(f"\nglossary_books.tsv: {len(filas)} términos usados en el mod "
          f"(de {len(libros)} en los glosarios)")
    print("por libro:", dict(collections.Counter(f[2] for f in filas)))


if __name__ == "__main__":
    main()
