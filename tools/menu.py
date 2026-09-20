#!/usr/bin/env python3
"""Menú para traducir con el agente local (Jan) sin recordar órdenes.

Uso (desde cualquier carpeta):  python tools/menu.py

Cada opción sigue la receta equivalente de AGENTS.md: prepara los lotes con
pod.py y lanza tools/local_agent.py, que termina con «el cierre».
build, la versión y git siguen siendo cosa del usuario.
Solo librería estándar.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

# line_buffering: que los títulos salgan antes que la salida de los scripts que lanza.
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from local_agent import JAN_URL, jan_models, unload_others  # noqa: E402

EN_DIR = json.loads((ROOT / "tools" / "config.json").read_text(encoding="utf-8"))["en_dir"]
TODO = ROOT / "work_queue" / "todo"
RULES = [
    ("tokens", "marcas del juego perdidas o cambiadas (la más importante)"),
    ("glossary", "términos del glosario no respetados"),
    ("english", "palabras inglesas sueltas"),
    ("display", "texto de Glossary(...) o Concept(...) sin traducir"),
    ("punct", "faltan ¿ o ¡"),
    ("custom", "funciones de género inexistentes"),
    ("spaces", "espacios sobrantes"),
]


# ── utilidades ──────────────────────────────────────────────────────────────

def run(*args):
    """Ejecuta un script de tools/ mostrando su salida en directo. Devuelve True si ha ido bien."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / args[0])] + list(args[1:]), cwd=ROOT)
    return r.returncode == 0


def pod(*args):
    return run("pod.py", *args)


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    except EOFError:
        v = ""
    return v or default


def yes(prompt, default=False):
    v = ask(f"{prompt} (s/n)", "s" if default else "n").lower()
    return v.startswith("s")


def ask_int(prompt, default):
    while True:
        v = ask(prompt, str(default))
        if v.isdigit() and int(v) > 0:
            return int(v)
        print("  Escribe un número mayor que 0.")


def queued(prefix):
    return sorted(TODO.glob(f"{prefix}*.txt")) if TODO.exists() else []


def title(t):
    print(f"\n══ {t} " + "═" * max(0, 60 - len(t)))


def choose_model():
    """Pide elegir un modelo de Jan y descarga los demás. Devuelve su id, o None si no se puede seguir."""
    try:
        urllib.request.urlopen(JAN_URL.rstrip("/") + "/models", timeout=5).close()
    except Exception:
        print(f"\n✘ Jan no responde en {JAN_URL}.\n"
              "  Abre Jan y activa Ajustes → Local API Server.\n"
              "  Los lotes preparados se quedan en la cola: usa «Seguir con la cola» cuando esté listo.")
        return None
    models = jan_models()
    if not models:
        print("\n✘ No consigo la lista de modelos de Jan (¿tienes alguno descargado?).")
        return None
    loaded = [m["id"] for m in models if m["loaded"]]
    print("\nModelos de Jan:")
    for i, m in enumerate(models, 1):
        print(f"  {i}. {m['id']}{'   ← cargado' if m['loaded'] else ''}")
    default = models.index(next(m for m in models if m["id"] == loaded[0])) + 1 if len(loaded) == 1 else 1
    while True:
        v = ask("Modelo", str(default))
        if v.isdigit() and 1 <= int(v) <= len(models):
            model = models[int(v) - 1]["id"]
            break
        print("  Elige un número de la lista.")
    for name in unload_others(model):
        print(f"  Descargado de Jan: {name}")
    if model not in loaded:
        print(f"  Jan cargará {model} con el primer lote (puede tardar un poco).")
    return model


def agent(prefix=None):
    """Lanza el agente local sobre la cola (con el prefijo dado) y hace el cierre."""
    model = choose_model()
    if not model:
        return
    title("Traduciendo con el agente local (Ctrl+C para parar; el lote en curso no se pierde)")
    run("local_agent.py", *(["--prefix", prefix] if prefix else []), "--model", model, "--close")
    mdir = ROOT / "work_queue" / "manual"
    n = sum(len(json.loads(f.read_text(encoding="utf-8"))) for f in mdir.glob("*.json")) if mdir.exists() else 0
    if n:
        print(f"\n⚠ Hay {n} textos en work_queue/manual/ que no han pasado la validación: usa la opción"
              "\n  «Traducir lo apartado en manual/» (van como lotes M, aparte del resto) o revísalos a mano.")
    print("\nRevisa el diff de spanish/. build, la versión y git son cosa tuya.")


# ── opciones del menú ───────────────────────────────────────────────────────

def update():
    title("Actualización de Princes of Darkness")
    if queued("U") and yes(f"Ya hay {len(queued('U'))} lotes U en la cola. ¿Traducirlos sin volver a sincronizar?", True):
        return agent("U")
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--", EN_DIR], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        print(f"✘ No encuentro git: hace falta para saber qué ha cambiado en {EN_DIR}/.")
        return
    if r.returncode:
        print(f"✘ git ha fallado:\n{r.stderr}")
        return
    if r.stdout.strip():
        print(f"✘ {EN_DIR}/ tiene cambios sin commitear. Haz commit del inglés nuevo y vuelve a intentarlo.")
        return
    print("Esto es lo que cambiaría (simulación):\n")
    if not pod("sync", "--dry-run"):
        return
    if not yes("\n¿Aplicar la sincronización y preparar los lotes de la actualización?", True):
        return
    if pod("sync") and pod("batch", "--scope", "update"):
        if queued("U"):
            agent("U")
        else:
            print("\nNo hay nada nuevo que traducir.")


def pending():
    title("Traducir pendientes")
    pod("status")
    if queued("B"):
        print(f"\nYa hay {len(queued('B'))} lotes B en la cola.")
        if not yes("¿Preparar además lotes nuevos?"):
            return agent("B")
    n = ask_int("\n¿Cuántos lotes preparar? (unos 30 s cada uno)", 10)
    zone = ask("Zona concreta, p. ej. traits/* (Intro = todo, en el orden de prioridad)")
    if pod("batch", "--limit", str(n), *(["--files", zone] if zone else [])):
        agent("B")


def review():
    title("Corrección de lo traducido")
    if yes("¿Ver primero los arreglos automáticos sin IA (fix)?"):
        pod("fix", "--dry-run")
        if yes("¿Aplicarlos?"):
            pod("fix")
    print("\nReglas de revisión:")
    for i, (r, d) in enumerate(RULES, 1):
        print(f"  {i}. {r:<9} {d}")
    while True:
        v = ask("Regla", "1")
        if v.isdigit() and 1 <= int(v) <= len(RULES):
            rule = RULES[int(v) - 1][0]
            break
        print("  Elige un número de la lista.")
    zone = ask("Archivos, p. ej. traits/* (Intro = todos)")
    files = ["--files", zone] if zone else []
    title(f"Informe: {rule}")
    if not pod("check", "--rule", rule, *files):
        return
    if not yes("\n¿Preparar lotes de corrección con esto?", True):
        return
    n = ask_int("¿Cuántos lotes como máximo?", 10)
    if pod("batch", "--mode", "review", "--rule", rule, "--limit", str(n), *files):
        if queued("R"):
            agent("R")
        else:
            print("\nNo hay nada que corregir con esa regla.")


def resume():
    title("Seguir con la cola")
    if not any(queued(p) for p in "UBRNM"):
        print("La cola está vacía.")
        return
    agent()


def status():
    title("Estado")
    pod("status")


def manual():
    title("Traducir lo apartado en manual/")
    n = sum(len(json.loads(f.read_text(encoding="utf-8"))) for f in (ROOT / "work_queue" / "manual").glob("*.json"))
    if not n and not queued("M"):
        print("No hay nada en work_queue/manual/.")
        return
    if n:
        print(f"{n} textos apartados. Se devuelven a la cola como lotes M, aparte de los demás,")
        print("para que esto no se cruce con otro agente que esté traduciendo.")
        if not yes("¿Devolverlos a la cola?", True) or not pod("clean", "--requeue"):
            return
    agent("M")


def clean():
    title("Limpiar la cola")
    pod("clean", "--dry-run")
    if yes("¿Aplicar la limpieza?", True):
        pod("clean")
    manual = ROOT / "work_queue" / "manual"
    if any(manual.glob("*.json")) and yes("¿Devolver a la cola lo que sigue en manual/ para traducirlo otra vez?"):
        pod("clean", "--requeue")


MENU = [
    ("Actualizar (traducir lo nuevo de una versión de PoD)", update),
    ("Traducir pendientes", pending),
    ("Corregir lo traducido", review),
    ("Seguir con la cola (lotes ya preparados)", resume),
    ("Ver estado", status),
    ("Traducir lo apartado en manual/", manual),
    ("Limpiar la cola", clean),
]


def main():
    while True:
        title("Princes of Darkness · traducción con agente local")
        for i, (label, _) in enumerate(MENU, 1):
            print(f"  {i}. {label}")
        print("  0. Salir")
        v = ask("Opción")
        if v == "0":
            return
        if not (v.isdigit() and 1 <= int(v) <= len(MENU)):
            continue
        try:
            MENU[int(v) - 1][1]()
        except KeyboardInterrupt:
            print("\nInterrumpido. Lo que quedaba sin aplicar sigue en work_queue/todo.")
        ask("\nIntro para volver al menú")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
