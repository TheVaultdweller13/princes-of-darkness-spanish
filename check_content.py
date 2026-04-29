#!/usr/bin/env python3
"""
Compara dos archivos de localización y muestra las claves presentes en A pero no en B.
Usa regex para evitar dependencias externas. Compatible con claves tipo Paradox.
"""

import sys
import re
from pathlib import Path

def extraer_claves(ruta):
    """Devuelve un conjunto de todas las claves del archivo."""
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    claves = set()
    # Acepta puntos y guiones bajos, típico en localización de Paradox
    patron = re.compile(r'^[ \t]*([a-zA-Z0-9_.]+)[ \t]*:')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith('#'):
            continue
            
        match = patron.match(linea)
        if match:
            clave = match.group(1)
            # Opcional: ignorar la clave raíz del idioma (l_english, l_spanish, etc.)
            if clave.startswith('l_'):
                continue
            claves.add(clave)
            
    return claves

def main():
    if len(sys.argv) != 3:
        print("Uso: python compare_loc.py <archivo_A.yml> <archivo_B.yml>")
        sys.exit(1)

    file1 = Path(sys.argv[1])
    file2 = Path(sys.argv[2])

    if not file1.is_file() or not file2.is_file():
        print("❌ Error: Uno de los archivos no existe.")
        sys.exit(1)

    print(f"Comparando:\n  📄 {file1.name}\n  📄 {file2.name}\n")

    claves_a = extraer_claves(file1)
    claves_b = extraer_claves(file2)

    faltantes = claves_a - claves_b

    if faltantes:
        print(f"⚠️  {len(faltantes)} clave(s) en {file1.name} que faltan en {file2.name}:")
        for clave in sorted(faltantes):
            print(f"  - {clave}")
        sys.exit(1)  # Exit code 1 para CI/CD o scripts de automatización
    else:
        print("✅ Todas las claves están presentes en ambos archivos.")
        sys.exit(0)

if __name__ == "__main__":
    main()