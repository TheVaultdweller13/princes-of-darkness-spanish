#!/usr/bin/env python3
"""Agente local: traduce los lotes de work_queue con el servidor local de Jan.

Hace lo mismo que el «bucle» de tools/TRADUCIR_LOTE.md, pero sin que el modelo
tenga que ejecutar órdenes: este script pide el lote con `pod.py next`, se lo
pasa al modelo, guarda la respuesta en work_queue/out/ y ejecuta `pod.py apply`.
Solo librería estándar. Sirve cualquier servidor compatible con OpenAI (--url).

Uso (desde la raíz del repositorio, con el Local API Server de Jan arrancado
y UN modelo cargado; el script usa el que esté cargado):
  python tools/local_agent.py --prefix B --limit 5          # 5 lotes pendientes
  python tools/local_agent.py --prefix U --close             # actualización + el cierre

Preparar los lotes (sync / batch) sigue siendo cosa de `pod.py`: ver AGENTS.md.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
POD = [sys.executable, str(ROOT / "tools" / "pod.py")]
Q = ROOT / "work_queue"

JAN_URL = "http://127.0.0.1:1337/v1"
ALIAS_RE = re.compile(r'--alias\s+(?:"([^"]+)"|(\S+))')
PORT_RE = re.compile(r"--port\s+(\d+)")

# ── Modelos de Jan ────────────────────────────────────────────────────────────
# Jan exige el nombre del modelo en cada petición y carga el que se le pida aunque ya
# haya otro en marcha; su API pública no dice cuál está cargado ni permite descargarlos.
# Por debajo, Jan lanza un llama-server «router» (--models-preset) que sí informa del
# estado de cada modelo, y un llama-server por modelo cargado (--alias <modelo>).
# Cerrar ese proceso descarga el modelo: el router lo marca como descargado.


def _llama_processes():
    """[(pid, línea de órdenes)] de los llama-server en marcha, o None si no se puede consultar."""
    try:
        if os.name == "nt":
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
                   "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"]
        else:
            cmd = ["ps", "-axww", "-o", "pid=,args="]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    procs = []
    for line in out.splitlines():
        pid, _, args = line.strip().partition("\t" if os.name == "nt" else " ")
        if pid.isdigit() and "llama-server" in args:
            procs.append((int(pid), args))
    return procs


def _alias(args):
    m = ALIAS_RE.search(args)
    return m and (m.group(1) or m.group(2))


def jan_models():
    """[{'id', 'loaded'}] de los modelos de chat de Jan, o None si no se encuentra su router."""
    procs = _llama_processes() or []
    router = next((a for _, a in procs if "--models-preset" in a), None)
    port = router and PORT_RE.search(router)
    if not port:
        return None
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port.group(1)}/models", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))["data"]
    except (OSError, ValueError, KeyError):
        return None
    return [{"id": m["id"], "loaded": m.get("status", {}).get("value") == "loaded"}
            for m in data if "--embeddings" not in m.get("status", {}).get("args", [])]


def unload_others(keep):
    """Descarga de Jan todos los modelos cargados salvo `keep` (None = todos). Devuelve los descargados."""
    done = []
    for pid, args in _llama_processes() or []:
        name = _alias(args)
        if name and name != keep:
            try:
                os.kill(pid, signal.SIGTERM)
                done.append(name)
            except OSError:
                pass
    if done:
        time.sleep(2)  # que el router de Jan registre el cierre antes de la siguiente petición
    return done


def pick_model():
    """El único modelo de chat cargado en Jan, o (None, motivo) si no se puede decidir sin riesgo."""
    models = jan_models()
    if models is None:
        return None, "no puedo ver qué modelo tiene cargado Jan: indícalo con --model"
    loaded = [m["id"] for m in models if m["loaded"]]
    if not loaded:
        return None, "Jan no tiene ningún modelo cargado: carga uno antes de traducir (o usa el menú, que te deja elegirlo)"
    if len(loaded) > 1:
        return None, ("Jan tiene varios modelos cargados a la vez (" + ", ".join(loaded) +
                      "): descarga los que sobren o usa el menú, que lo hace por ti")
    return loaded[0], ""


LINE_RE = re.compile(r"^\s*(\d+)\s*=\s?(.*)$")
THINK_RE = re.compile(r"<think>.*?</think>", re.S)

PREAMBLE = """Eres un traductor profesional de videojuegos del inglés al castellano (España).
Traduces la localización del mod «Princes of Darkness» (Crusader Kings III, Mundo de Tinieblas).

FORMATO DE RESPUESTA (obligatorio):
- Responde SOLO con líneas «<número> = <texto>», una por elemento, en el orden del lote.
- Nada más: sin explicaciones, sin comillas alrededor, sin bloques de código, sin repetir el inglés.
- Cada traducción en UNA sola línea: los saltos de línea del juego se escriben literalmente como \\n.
- En MODO REVISAR, MODO ESTILO o MODO NOMBRES escribe solo las líneas que cambies; si no cambias ninguna, responde «# sin cambios».
- En MODO ESTILO no cambiar es la respuesta normal: el texto español ya es correcto. Devuelve solo los que tengan un defecto concreto que sepas nombrar, y nunca los re-traduzcas desde el inglés.
- Si el lote trae «MOTIVO: RECHAZADO», corrige exactamente lo que dice el motivo.

A continuación, las reglas del proyecto:
"""


def pod(*args):
    r = subprocess.run(POD + list(args), cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode:
        sys.exit(f"pod.py {' '.join(args)} ha fallado:\n{r.stdout}{r.stderr}")
    return r.stdout


def system_prompt():
    rules = (ROOT / "tools" / "TRADUCIR_LOTE.md").read_text(encoding="utf-8")
    # El «Bucle de trabajo» describe órdenes que ejecuta este script, no el modelo.
    rules = rules[rules.index("## Reglas de idioma"):]
    return PREAMBLE + "\n" + rules


class ServerDown(Exception):
    """Jan no responde: no tiene sentido seguir ni apartar lotes."""


class BatchFailed(Exception):
    """Fallo propio de un lote (no cabe en el contexto, respuesta inservible, tiempo agotado…)."""


def server_alive(a):
    try:
        with urllib.request.urlopen(a.url.rstrip("/") + "/models", timeout=15):
            return True
    except Exception:
        return False


def chat(a, system, user):
    if not a.model:  # se decide con la primera petición: con la cola vacía no hace falta modelo
        a.model, why = pick_model()
        if not a.model:
            sys.exit(f"✘ {why}.")
        print(f"Modelo: {a.model}")
    url =a.url.rstrip("/") + "/chat/completions"
    # Temperatura baja: fidelidad y marcas del juego intactas antes que creatividad. top_k, repeat_penalty
    # y chat_template_kwargs (desactiva el razonamiento previo en los modelos que lo tienen) son extensiones de llama.cpp.
    body = {"model": a.model, "stream": False, "temperature": 0.3, "top_p": 0.8, "top_k": 20, "repeat_penalty": 1.05,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return THINK_RE.sub("", data["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        raise BatchFailed(f"el servidor ha respondido {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError) or "timed out" in str(e.reason):
            raise BatchFailed("tiempo de espera agotado")
        raise ServerDown(f"no se puede conectar con {url} ({e.reason}). ¿Está arrancado el Local API Server de Jan?")
    except TimeoutError:
        raise BatchFailed("tiempo de espera agotado")
    except OSError as e:  # conexión cortada a mitad: ¿se ha caído Jan o solo este lote?
        if server_alive(a):
            raise BatchFailed(f"conexión interrumpida ({e})")
        raise ServerDown(f"Jan ha dejado de responder ({e})")
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise BatchFailed(f"respuesta del servidor ilegible ({e})")


def parse(reply):
    lines = []
    for raw in reply.splitlines():
        m = LINE_RE.match(raw)
        if m:
            lines.append(f"{m.group(1)} = {m.group(2).rstrip()}")
    if not lines and "sin cambios" in reply.lower():
        return ["# sin cambios"]
    return lines


# Fallos seguidos sin ningún éxito entre medias. Dividir un lote de 40 hasta llegar a 1 texto son 6;
# más que esto apunta a un problema general (modelo, servidor), no a un lote concreto.
MAX_CONSECUTIVE_FAILURES = 8


def run_batches(a, prefix, limit, system, only=None):
    """Procesa lotes hasta el límite (en lotes de la cola) o hasta vaciarla. Con `only`, se limita a
    esa lista de lotes y no toca el resto de la cola. Un lote que falla entero se aparta (se divide
    en dos, o va a manual/ si es de un solo texto) y se sigue.

    `pendientes` son lotes derivados de los que ya se han empezado —mitades de uno dividido y
    reintentos de líneas rechazadas—: van primero y no gastan el límite, porque son la otra mitad
    del trabajo ya contado."""
    done = attempts = failures_in_a_row = sin_escribir = 0
    pendientes = list(only or [])
    while True:
        while pendientes and not (Q / "todo" / f"{pendientes[0]}.txt").exists():
            pendientes.pop(0)
        if pendientes:
            todo = Q / "todo" / f"{pendientes.pop(0)}.txt"
        elif only is not None:
            break  # la lista se ha agotado: el resto de la cola no es cosa nuestra
        elif limit is not None and attempts >= limit:
            quedan = len(list((Q / "todo").glob(f"{prefix or ''}*.txt")))
            print(f"Límite de {limit} lotes alcanzado" + (f" · quedan {quedan} en la cola" if quedan else ""))
            break
        else:
            nxt = pod("next", *(["--prefix", prefix] if prefix else []))
            m = re.search(r"SIGUIENTE:\s*(\S+\.txt)", nxt)
            if not m:
                print(nxt.strip())
                break
            todo = ROOT / m.group(1)
        name = todo.stem
        batch = todo.read_text(encoding="utf-8")
        n_items = len(re.findall(r"^(EN:|\d+: )", batch, re.M))
        attempts += 1
        t0 = time.time()
        try:
            lines = []
            for attempt in (1, 2):
                lines = parse(chat(a, system, batch))
                if lines:
                    break
                print(f"{name}: respuesta sin líneas «N = …», reintentando ({attempt}/2)")
            if not lines:
                raise BatchFailed("el modelo no ha devuelto nada utilizable")
        except ServerDown as e:
            a.server_down = True
            print(f"✘ {e}\n  Me detengo: el lote {name} sigue intacto en work_queue/todo.")
            break
        except BatchFailed as e:
            if a.dry_run:
                print(f"✘ {name}: {e}")
                break
            failures_in_a_row += 1
            print(f"✘ {name}: {e}")
            out = pod("setaside", name, "--reason", str(e)[:120], *(["--split"] if n_items > 1 else [])).rstrip()
            print(out)
            if "dividido en" in out:
                pendientes = re.findall(r"\b([UBRNMS]\d{4})\b", out.split("dividido en", 1)[1])[:2] + pendientes
            a.set_aside = getattr(a, "set_aside", 0) + 1
            if failures_in_a_row >= MAX_CONSECUTIVE_FAILURES:
                print(f"✘ {failures_in_a_row} lotes seguidos han fallado: parece un problema general, no de un lote. Me detengo.")
                break
            continue
        failures_in_a_row = 0
        print(f"{name}: {len(lines)}/{n_items} líneas en {time.time() - t0:.0f} s")
        if a.dry_run:
            print("\n".join(lines))
            break
        (Q / "out").mkdir(exist_ok=True)
        (Q / "out" / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        aplicado = pod("apply", name).rstrip()
        print(aplicado)
        # los reintentos de líneas rechazadas son continuación de este lote: se hacen ahora, no se
        # quedan en la cola engordándola para la próxima ejecución
        pendientes += re.findall(r"reintento en lote ([UBRNMS]\d{4})", aplicado)
        # si spanish/ no se deja escribir, seguir traduciendo es tirar el tiempo: el lote se guarda,
        # pero nada llega al disco. Se avisa y se para tras unos cuantos seguidos.
        if "NO se da por hecho" in aplicado:
            sin_escribir += 1
            if sin_escribir >= 3:
                print(f"✘ {sin_escribir} lotes seguidos sin poder escribir en spanish/: me detengo.\n"
                      "  Están guardados en work_queue/out/. Cuando el archivo esté libre, aplícalos con:\n"
                      "    python tools/pod.py apply --all")
                break
            continue
        sin_escribir = 0
        done += 1
    return done


def close(a, system):
    """«El cierre» de AGENTS.md: fix --dirty, verify --batch, una pasada R, clean y status."""
    print("── cierre: fix --dirty")
    print(pod("fix", "--dirty").rstrip())
    before = {p.stem for p in (Q / "todo").glob("R*.txt")}
    print("── cierre: verify --batch")
    print(pod("verify", "--batch", "--limit", str(a.close_limit)).rstrip())
    new = sorted({p.stem for p in (Q / "todo").glob("R*.txt")} - before)
    if new and getattr(a, "server_down", False):
        print(f"── cierre: {len(new)} lotes R quedan en la cola (Jan no responde)")
    elif new:
        # una sola pasada y solo sobre los lotes que acaba de crear verify: si tirásemos de la cola
        # cogeríamos los R viejos y estos se quedarían para siempre esperando
        print(f"── cierre: {len(new)} lotes R de verify")
        run_batches(a, "R", None, system, only=new)
        print(pod("verify").rstrip())
    print("── cierre: clean")
    print(pod("clean").rstrip())
    print(pod("status").rstrip())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", choices=["U", "B", "R", "N", "M", "S"], help="prefijo de los lotes (por defecto, el siguiente que haya)")
    p.add_argument("--limit", type=int, help="máximo de lotes en esta ejecución")
    p.add_argument("--close", action="store_true", help="hacer «el cierre» de AGENTS.md al terminar")
    p.add_argument("--close-limit", type=int, default=10, help="máximo de lotes de corrección que puede crear el cierre")
    p.add_argument("--dry-run", action="store_true", help="traduce el siguiente lote y lo muestra, sin guardar ni aplicar")
    p.add_argument("--url", default=JAN_URL, help="API compatible con OpenAI (por defecto, Jan)")
    p.add_argument("--model", help="id del modelo en Jan (por defecto, el único que esté cargado)")
    p.add_argument("--keep-loaded", action="store_true", help="no descargar el modelo de Jan al terminar")
    p.add_argument("--timeout",type=int, default=900, help="segundos máximos por lote")
    a = p.parse_args()

    system = system_prompt()
    try:
        n = run_batches(a, a.prefix, a.limit, system)
        if a.close and not a.dry_run:
            close(a, system)
        apartados = getattr(a, "set_aside", 0)
        print(f"Lotes procesados: {n}" + (f" · lotes apartados por fallo: {apartados}" if apartados else "") +
              ". Recuerda: build, versión y git los haces tú.")
    finally:
        # Pase lo que pase (fin, error o Ctrl+C), no dejar modelos ocupando la GPU.
        # El servidor de Jan sigue en marcha: solo se descargan los modelos.
        if a.model and not a.keep_loaded:
            for name in unload_others(None):
                print(f"Modelo descargado de Jan: {name}")


if __name__ == "__main__":
    main()
