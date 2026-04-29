import os

def find_files_missing_translation(spanish_dir, english_dir):
    """Busca archivos en inglés que no tienen su equivalente en español"""
    
    missing_files = []
    
    # Recorrer todos los archivos en el directorio inglés
    for root, dirs, files in os.walk(english_dir):
        for file in files:
            if file.endswith('_english.yml'):
                # Obtener la ruta relativa desde el directorio inglés
                rel_path = os.path.relpath(root, english_dir)
                
                # Construir el nombre del archivo en español (reemplazar _english.yml por _spanish.yml)
                spanish_file = file.replace('_english.yml', '_spanish.yml')

                if spanish_file == "00_aliases_for_ctd_fixes_POD_l_spanish.yml":

                    print(f"DEBUG: Verificando archivo: {spanish_file} en {rel_path}")
                
                # Construir la ruta completa donde debería estar el archivo en español
                spanish_path = os.path.join(spanish_dir, rel_path, spanish_file)
                
                # Verificar si existe
                if not os.path.exists(spanish_path):
                    missing_files.append(os.path.join(rel_path, file))
    
    return missing_files

if __name__ == "__main__":
    spanish_dir = r"D:\Princes of Darkness - Traducción\working\spanish"
    english_dir = r"D:\Princes of Darkness - Traducción\original_text\english"
    print(f"Comparando:\n'{spanish_dir}'\n'{english_dir}'\n")

    if not os.path.exists(spanish_dir):
        print(f"ERROR: El directorio no existe: {spanish_dir}")
    elif not os.path.exists(english_dir):
        print(f"ERROR: El directorio no existe: {english_dir}")
    else:
        missing = find_files_missing_translation(spanish_dir, english_dir)
        
        print("=" * 80)
        print(f"ARCHIVOS FALTANTES EN ESPAÑOL ({len(missing)} archivos)")
        print("=" * 80)
        
        if missing:
            for file in sorted(missing):
                print(f"  FALTA: {file}")
        else:
            print("\n✅ Todos los archivos l_english tienen su equivalente l_spanish.")
        
        print("=" * 80)