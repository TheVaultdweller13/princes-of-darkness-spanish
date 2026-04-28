#!/usr/bin/env python3
"""
Compara dos archivos de localización y muestra las claves presentes en A pero no en B.
Sin parsear YAML, solo extrayendo claves con regex.
"""

import sys
import re
from pathlib import Path

def extraer_claves(ruta):
    """Devuelve un conjunto de todas las claves (etiquetas) del archivo."""
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    claves = set()
    # Patrón: ignora espacios iniciales, captura la clave (letras, números, guiones bajos),
    # seguida de ':' opcionalmente rodeado de espacios y luego cualquier cosa.
    patron = re.compile(r'^[ \t]*([a-zA-Z0-9_]+)[ \t]*:')
    for linea in lineas:
        # Ignorar líneas que empiezan con '#' (comentarios)
        if linea.lstrip().startswith('#'):
            continue
        match = patron.match(linea)
        if match:
            claves.add(match.group(1))
    return claves

def main():
    # Rutas (ajústalas si es necesario)
    archivo_a = Path("original_text/english/decisions/POD_decisions_l_english.yml")
    archivo_b = Path("working/spanish/decisions/POD_decisions_l_spanish.yml")

    if not archivo_a.is_file() or not archivo_b.is_file():
        print("Error: Uno de los archivos no existe.")
        sys.exit(1)

    claves_a = extraer_claves(archivo_a)
    claves_b = extraer_claves(archivo_b)

    faltantes = claves_a - claves_b

    if faltantes:
        print(f"Claves en {archivo_a.name} que faltan en {archivo_b.name}:")
        for clave in sorted(faltantes):
            print(f"  - {clave}")
    else:
        print("Todas las claves de l_english están presentes en l_spanish.")

if __name__ == "__main__":
    main()