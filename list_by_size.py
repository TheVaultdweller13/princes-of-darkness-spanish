import os
import sys

def buscar_archivos_l_english(directorio_raiz):
    """
    Busca recursivamente archivos .yml que contengan el tag 'l_english:' al inicio
    y los lista ordenados por número de líneas.
    """
    resultados = []

    # Recorrer todas las subcarpetas
    for ruta_actual, carpetas, ficheros in os.walk(directorio_raiz):
        for nombre in ficheros:
            # Filtro opcional: si solo te interesan archivos que terminan en spanish.yml
            # puedes descomentar la siguiente línea. Si quieres buscar en TODOS los yml, déjala comentada.
            # if not nombre.endswith('_spanish.yml'): continue 
            
            if nombre.endswith('.yml'):
                ruta_completa = os.path.join(ruta_actual, nombre)
                try:
                    with open(ruta_completa, 'r', encoding='utf-8-sig') as f:
                        lineas_totales = 0
                        tiene_tag = False
                        
                        # Leer línea a línea para buscar el tag y contar
                        for linea in f:
                            lineas_totales += 1
                            # Solo necesitamos encontrar el tag una vez
                            if not tiene_tag:
                                linea_limpia = linea.strip()
                                # Ignorar líneas vacías o comentarios para encontrar el tag real
                                if linea_limpia and not linea_limpia.startswith('#'):
                                    if linea_limpia.startswith('l_english:'):
                                        tiene_tag = True
                                    # Si encontramos la primera línea válida y no es el tag, 
                                    # podemos dejar de buscar el tag para ahorrar tiempo, 
                                    # pero seguiremos leyendo para contar líneas.
                                    elif not tiene_tag and linea_limpia != '':
                                        # Si la primera línea de código no es l_english:, 
                                        # asumimos que este archivo no cumple la condición 
                                        # (esto optimiza la búsqueda si el tag debe estar al inicio).
                                        # Si el tag puede estar en cualquier parte, borra este 'break'.
                                        # Para este caso, asumiremos que debe estar al inicio o ser la línea principal.
                                        # Si quieres buscar la cadena en cualquier lugar del archivo, elimina este bloque.
                                        pass 

                        if tiene_tag:
                            resultados.append((lineas_totales, ruta_completa))

                except Exception as e:
                    print(f"[!] Error al leer {ruta_completa}: {e}", file=sys.stderr)

    # Ordenar por número de líneas (menor a mayor)
    resultados.sort(key=lambda x: x[0])

    return resultados

if __name__ == '__main__':
    # Directorio por defecto o pasado por argumento
    raiz = sys.argv[1] if len(sys.argv) > 1 else r"D:\Princes of Darkness - Traducción\working\spanish"
    
    print(f"Analizando directorio: {raiz}...")
    archivos = buscar_archivos_l_english(raiz)
    
    print(f"\nEncontrados {len(archivos)} archivos con tag 'l_english:'\n")
    print(f"{'LÍNEAS':<10} | {'RUTA'}")
    print("-" * 80)
    
    for lineas, ruta in archivos:
        print(f"{lineas:<10} | {ruta}")