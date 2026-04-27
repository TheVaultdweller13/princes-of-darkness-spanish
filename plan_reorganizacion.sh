#!/bin/bash

# Script para sincronizar estructura de archivos entre inglés y español
# Compara archivos *_english / *_spanish

echo "=== SINCRONIZACIÓN DE ESTRUCTURA DE ARCHIVOS ==="
echo "Comparando: original_text/english ↔ spanish_translation/localization/spanish"
echo ""

# Rutas base
ENGLISH_BASE="original_text/english"
SPANISH_BASE="spanish_translation/localization/spanish"

# Contadores
created=0
deleted=0
ignored=0

# 1. CREAR ARCHIVOS FALTANTES EN ESPAÑOL
echo "--- BUSCANDO ARCHIVOS FALTANTES EN ESPAÑOL ---"

find "$ENGLISH_BASE" -type f -name "*_english.yml" | while read english_file; do
    # Obtener la ruta relativa desde la base inglesa
    relative_path="${english_file#$ENGLISH_BASE/}"
    
    # Generar el nombre del archivo en español (sustituir _english por _spanish)
    spanish_file="${relative_path//_english.yml/_spanish.yml}"
    spanish_full_path="$SPANISH_BASE/$spanish_file"
    
    # Si el archivo en español no existe, crearlo
    if [ ! -f "$spanish_full_path" ]; then
        # Crear directorio si no existe
        mkdir -p "$(dirname "$spanish_full_path")"
        touch "$spanish_full_path"
        echo "✅ CREADO: $spanish_file"
        ((created++))
    else
        ((ignored++))
    fi
done

echo ""

# 2. ELIMINAR ARCHIVOS OBSOLETOS EN ESPAÑOL
echo "--- BUSCANDO ARCHIVOS OBSOLETOS EN ESPAÑOL ---"

find "$SPANISH_BASE" -type f -name "*_spanish.yml" | while read spanish_file; do
    # Obtener la ruta relativa desde la base española
    relative_path="${spanish_file#$SPANISH_BASE/}"
    
    # Generar el nombre del archivo en inglés (sustituir _spanish por _english)
    english_file="${relative_path//_spanish.yml/_english.yml}"
    english_full_path="$ENGLISH_BASE/$english_file"
    
    # Si el archivo en inglés no existe, eliminar el español
    if [ ! -f "$english_full_path" ]; then
        rm "$spanish_file"
        echo "🗑️  ELIMINADO: $relative_path"
        ((deleted++))
    else
        ((ignored++))
    fi
done

# 3. MOSTRAR ESTADÍSTICAS
echo ""
echo "=== RESUMEN ==="
echo "Archivos creados: $created"
echo "Archivos eliminados: $deleted" 
echo "Archivos ignorados (ya existían): $ignored"
echo ""
echo "Sincronización completada."
