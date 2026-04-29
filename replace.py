#!/usr/bin/env python3
"""
Renombra recursivamente archivos que contengan 'l_english' en el nombre,
reemplazándolo por 'l_spanish'. Ej: archivo1_l_english.yml -> archivo1_l_spanish.yml
"""
import sys
from pathlib import Path

# 📁 Ruta objetivo (r"" evita conflictos con \)
BASE_DIR = Path(r"D:\Princes of Darkness - Traducción\working\cambiar_sufijo_nombre_archivo")

if not BASE_DIR.is_dir():
    print(f"❌ Error: La carpeta no existe o no es accesible:\n   {BASE_DIR}")
    sys.exit(1)

print(f"🔍 Escaneando recursivamente en: {BASE_DIR}")
print("⏳ Procesando archivos...\n")

renombrados = 0
omitidos = 0

for archivo in BASE_DIR.rglob('*'):
    if not archivo.is_file():
        continue
        
    # Filtrar solo archivos que contengan l_english en el nombre
    if 'l_english' not in archivo.name:
        continue

    nuevo_nombre = archivo.name.replace('l_english', 'l_spanish')
    nueva_ruta = archivo.with_name(nuevo_nombre)

    if nueva_ruta.exists():
        print(f"⏭️ Omitido: {archivo.name} (ya existe {nuevo_nombre})")
        omitidos += 1
    else:
        print(f"✅ Renombrando: {archivo.name} -> {nuevo_nombre}")
        archivo.rename(nueva_ruta)
        renombrados += 1

print(f"\n🏁 Finalizado: {renombrados} renombrado(s), {omitidos} omitido(s).")