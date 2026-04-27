import os
import sys

def buscar_y_ordenar_spanish_yml(directorio_raiz='.'):
    """
    Busca recursivamente archivos *_spanish.yml que empiecen con 'l_english:',
    cuenta sus líneas y los muestra ordenados de menor a mayor.
    """
    archivos = []

    for ruta_actual, carpetas, ficheros in os.walk(directorio_raiz):
        for nombre in ficheros:
            if nombre.endswith('spanish.yml'):
                ruta_completa = os.path.join(ruta_actual, nombre)
                try:
                    with open(ruta_completa, 'r', encoding='utf-8-sig') as f:
                        # Leer la primera línea no vacía
                        primera_linea = ''
                        for linea in f:
                            linea_limpia = linea.strip()
                            if linea_limpia:          # ignorar líneas en blanco
                                primera_linea = linea_limpia
                                break

                        # Verificar si empieza exactamente con "l_english:"
                        if primera_linea == 'l_english:':
                            # Contar el total de líneas del archivo
                            f.seek(0)
                            num_lineas = sum(1 for _ in f)
                            archivos.append((num_lineas, ruta_completa))
                except Exception as e:
                    print(f"Error al leer {ruta_completa}: {e}", file=sys.stderr)

    # Ordenar por número de líneas (menor a mayor)
    archivos.sort(key=lambda x: x[0])

    # Mostrar resultado
    for lineas, ruta in archivos:
        print(f"{lineas:>6} líneas: {ruta}")
    print(f"Total de archivos encontrados: {len(archivos)}")

if __name__ == '__main__':
    # Se puede pasar un directorio como argumento; si no, se usa el actual
    raiz = sys.argv[1] if len(sys.argv) > 1 else '.'
    buscar_y_ordenar_spanish_yml(raiz)