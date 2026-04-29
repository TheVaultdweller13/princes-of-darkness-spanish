#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Traductor robusto para localización de CK3 (Princes of Darkness)
Preserva $variables$, [tags], #formatos y \n usando marcadores <<VAR0>>.
MÉTODO: Separa texto y marcadores, traduce solo el texto, y reconstruye.
"""

import re
import requests
import sys
from pathlib import Path

class CK3Localizer:
    def __init__(self, api_url="http://127.0.0.1:5000", src_lang="en", tgt_lang="es"):
        self.api_url = api_url.rstrip('/')
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.token_counter = 0

    def protect_ck3_syntax(self, text):
        """Reemplaza sintaxis CK3 por marcadores <<VAR0>>, <<VAR1>>, etc."""
        # Orden: Tags complejos -> Variables -> Formatos -> Saltos
        pattern = r'(\[[^\[\]]*\]|\$[A-Za-z_][A-Za-z0-9_]*(?:\|[A-Za-z])?\$|#[A-Za-z_]+(?:\{[^}]*\})?|\\[ntr])'

        def replacer(match):
            placeholder = f"<<VAR{self.token_counter}>>"
            self.token_counter += 1
            return placeholder

        return re.sub(pattern, replacer, text), re.findall(pattern, text)

    def translate_text(self, text, original_vars):
        """
        Separa marcadores y texto. Envía SOLO el texto a la API como array.
        Reconstruye la cadena final sin tocar los marcadores.
        """
        if not text or not text.strip():
            return text

        # 1. Separamos en partes: [texto, marcador, texto, marcador, texto...]
        parts = re.split(r'(<<VAR\d+>>)', text)
        
        # 2. Extraemos solo las partes traducibles (índices pares)
        translatable_parts = [parts[i] for i in range(0, len(parts), 2)]

        try:
            # LibreTranslate acepta 'q' como array. Traduce manteniendo el orden.
            response = requests.post(
                f"{self.api_url}/translate",
                json={
                    "q": translatable_parts,
                    "source": self.src_lang,
                    "target": self.tgt_lang,
                    "format": "text"
                },
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            response.raise_for_status()
            
            translated_data = response.json()["translatedText"]
            # Por compatibilidad con versiones antiguas que devuelven string en lugar de lista
            translated_parts = translated_data if isinstance(translated_data, list) else [translated_data]

            # 3. Reconstruimos intercalando marcadores originales y texto traducido
            result = []
            t_idx = 0
            for i in range(len(parts)):
                if i % 2 == 0:  # Índice par -> texto traducido
                    result.append(translated_parts[t_idx] if t_idx < len(translated_parts) else "")
                    t_idx += 1
                else:
                    var = parts[i]
                    # Extraemos el número del marcador para obtener la variable original
                    var_index = int(re.search(r'<<VAR(\d+)>>', var).group(1))
                    # Agregamos la variable original sin traducir y espacios adicionales, ya que el traductor los elimina
                    result.append(f" {original_vars[var_index]} ")
                    
            return "".join(result)

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️ Error de API: {e}")
            return text

    def process_line(self, line):
        """Procesa una línea de localización preservando estructura YAML"""
        if not line.strip() or line.strip().startswith('#'):
            return line
        
        # Extrae clave y contenido entre comillas
        match = re.match(r'^(\s*)([a-zA-Z_][\w]*:\s*)"(.*?)"(\s*)$', line)
        if not match:
            return line  # Línea sin formato estándar, se deja intacta

        indent, key, content, trailing = match.groups()
        self.token_counter = 0  # Reinicia contador por línea
        
        # 1. Proteger sintaxis
        protected = self.protect_ck3_syntax(content)
        # 2. Traducir (solo texto, marcadores se quedan fuera)
        translated = self.translate_text(protected[0], protected[1])
        
        return f'{indent}{key}"{translated}"{trailing}\n'

    def process_file(self, input_path, output_path):
        """Procesa el archivo completo"""
        input_file = Path(input_path)
        if not input_file.exists():
            print(f"❌ No se encontró: '{input_file}'")
            return

        print(f"📂 Leyendo: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        translated_lines = []
        total = len(lines)
        print(f"🚀 Traduciendo {total} líneas...")

        for i, line in enumerate(lines, 1):
            if line.strip() == "l_english:":
                translated_lines.append("l_spanish:\n")
                continue
            translated_lines.append(self.process_line(line))
            if i % 50 == 0:
                print(f"   ... {i}/{total}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(translated_lines)
        print(f"✅ Completado. Guardado en: {output_path}")



def main():
    # Configuración
    input_file = input("Introduce la ruta del archivo a traducir: ").strip()
    
    if not Path(input_file).exists():
        print(f"Error: El archivo '{input_file}' no existe")
        sys.exit(1)
    
    output_file = input("Introduce la ruta del archivo de salida (o Enter para automático): ").strip()
    if not output_file:
        output_file = None
    
    # Crear traductor y procesar
    translator = CK3Localizer("http://127.0.0.1:5000")
    translator.process_file(input_file, output_file)

if __name__ == "__main__":
    main()