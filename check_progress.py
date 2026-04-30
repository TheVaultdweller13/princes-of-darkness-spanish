#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para calcular el % de traducción de un mod de CK3.
Compara las claves de los archivos originales (l_english) con las claves
ya traducidas (l_spanish) en la carpeta de trabajo.
"""

import os
import re
from pathlib import Path

def count_keys_in_file(filepath):
    """Cuenta claves válidas en un archivo de localización, ignorando header, comentarios y líneas vacías."""
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"⚠️ No se pudo leer {filepath}: {e}")
        return None, 0

    if not lines:
        return None, 0

    lang = None
    key_count = 0
    # Clave CK3: comienza con letra/guion bajo, sigue con alfanuméricos/guiones, termina en ':'
    # Se añade '-' para cubrir posibles guiones en nombres de clave.
    key_pattern = re.compile(r'^\s*[a-zA-Z_][\w-]*\s*:')

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Detectar idioma (primera línea válida que empiece por "l_")
        if lang is None:
            if stripped.lower().startswith('l_'):
                lang = stripped.rstrip(':').strip().lower()
                continue
            else:
                lang = 'unknown'

        if key_pattern.match(line):
            key_count += 1

    return lang, key_count

def scan_directory(root_dir):
    """Escanea recursivamente todos los .yml de un directorio.
    Retorna: (total_english_keys, total_spanish_keys, files_processed, [(filename, detected_lang)])
    """
    english_keys = 0
    spanish_keys = 0
    processed_files = 0
    unknown_files = []

    root_path = Path(root_dir)
    yml_files = list(root_path.rglob('*.yml'))
    print(f"🔍 Encontrados {len(yml_files)} archivos .yml en {root_dir}. Escaneando...")

    for filepath in yml_files:
        lang, count = count_keys_in_file(filepath)
        if lang == 'l_english':
            english_keys += count
        elif lang == 'l_spanish':
            spanish_keys += count
        elif lang is not None:
            unknown_files.append((filepath.name, lang))
        processed_files += 1

    return english_keys, spanish_keys, processed_files, unknown_files

def main():
    print("📊 Calculadora de progreso de traducción para CK3\n")

    # Rutas (usa barras normales para evitar escapes, o raw strings si usas \)
    en_dir = 'D:/Princes of Darkness - Traducción/original_text/english'
    es_dir = 'D:/Princes of Darkness - Traducción/working/spanish'

    print(f"📂 Directorio original (inglés):  {en_dir}")
    print(f"📂 Directorio traducción:         {es_dir}")

    if not os.path.isdir(en_dir):
        print("❌ La ruta del inglés original no es un directorio válido.")
        return
    if not os.path.isdir(es_dir):
        print("❌ La ruta de la traducción en español no es un directorio válido.")
        return

    # Escanear los originales -> solo interesan las claves de l_english
    total_en, _, processed_en, unknown_en = scan_directory(en_dir)
    # Escanear la traducción -> solo interesan las claves de l_spanish
    _, total_es, processed_es, unknown_es = scan_directory(es_dir)

    if processed_en != processed_es:
        print(f"⚠️  Número de archivos procesados no coincide: {processed_en} en inglés vs {processed_es} en español.")
    all_unknown = unknown_en + unknown_es

    print("\n" + "=" * 50)
    print(f"🇬🇧 Claves originales (l_english): {total_en}")
    print(f"🇪🇸 Claves traducidas (l_spanish): {total_es}")
    print("=" * 50)

    if total_en == 0:
        print("⚠️  No se encontraron claves en inglés. No se puede calcular el porcentaje.")
    else:
        progress = (total_es / total_en) * 100
        print(f"📈 Progreso de traducción: {progress:.2f}%")

        bar_len = 30
        filled = int(bar_len * progress / 100)
        bar = '█' * filled + '░' * (bar_len - filled)
        print(f"[{bar}] {progress:.1f}%")
    print("=" * 50)

    if all_unknown:
        print("\n⚠️  Archivos con idioma no reconocido o sin header válido:")
        for name, lang in all_unknown[:5]:
            print(f"   - {name} (detectado: {lang})")
        if len(all_unknown) > 5:
            print(f"   ... y {len(all_unknown) - 5} más.")

if __name__ == "__main__":
    main()