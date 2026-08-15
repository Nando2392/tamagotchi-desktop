# test_live.py — Verificación en vivo: mainloop REAL + event_generate real en cada botón.
# Dispara eventos Tk auténticos (<Button-1> con coordenadas) sobre cada botón,
# verifica el efecto en el pet, y cierra solo. Imprime un reporte.
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tama_live_")

import tkinter as tk

import tamagotchi_art as art
from tamagotchi_app import TamagotchiApp

results = []
root = tk.Tk()
app = TamagotchiApp(root, pos=(80, 80))

STAGE = {"feed": "feed", "play": "play", "bathe": "bathe", "sleep": "sleep"}


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS" if ok else "FAIL"), name, detail)


def real_click(bx, by):
    # evento Tk real con coordenadas de ventana, disparado sobre el canvas
    # (ahí es donde están los bindings de botones). El botón CERRAR destruye
    # el root dentro del handler, así que todo puede lanzar TclError.
    try:
        app.canvas.event_generate("<Button-1>", x=bx, y=by)
        try:
            root.update()
        except Exception:
            pass
        app.canvas.event_generate("<ButtonRelease-1>", x=bx, y=by)
        try:
            root.update()
        except Exception:
            pass
    except Exception:
        pass


def step(n):
    if n >= len(PLAN):
        finish()
        return
    name, fn, check = PLAN[n]
    try:
        fn()
        try:
            root.update()
        except Exception:
            pass  # la app pudo cerrarse (botón CERRAR) -> root destruido
        ok = check()
    except Exception as e:
        ok, check = False, repr(e)
    record(name, ok, "" if ok else f"({check})" if callable(check) else str(check))
    root.after(250, lambda: step(n + 1))


def finish():
    app.quit()
    failed = [r for r in results if not r[1]]
    print("\nLIVE:", "OK" if not failed else f"{len(failed)} FALLOS")
    print(json_dump([{"name": n, "ok": o} for n, o, _ in results]))
    root.quit()
    sys.exit(1 if failed else 0)


import json


def json_dump(o):
    return json.dumps(o, ensure_ascii=False)


# --- plan de verificación: cada botón con su efecto ---
pet = app.pet

# forzar estado bebé sano con stats conocidas
def setup_baby():
    pet.stage = "baby"
    pet.hunger = 50.0
    pet.happiness = 50.0
    pet.hygiene = 50.0
    pet.energy = 70.0
    pet.sick = False
    pet.sleeping = False
    pet.poop = 0


def click_feed():
    setup_baby()
    real_click(*art.BUTTONS["feed"][:2])


def click_play():
    setup_baby()
    real_click(*art.BUTTONS["play"][:2])


def click_bathe():
    setup_baby()
    real_click(*art.BUTTONS["bathe"][:2])


def click_sleep_on():
    setup_baby()
    real_click(*art.BUTTONS["sleep"][:2])


def click_sleep_off():
    pet.sleeping = True
    real_click(*art.BUTTONS["sleep"][:2])


def click_poop():
    setup_baby()
    pet.poop = 1
    sx, sy = art.POOP_SLOTS[0]
    real_click(sx, sy)


def click_close():
    # el botón de cerrar debe disparar quit() sin excepción
    x0, y0, x1, y1 = art.CLOSE_RECT
    real_click((x0 + x1) // 2, (y0 + y1) // 2)


moved = False


def drag_test():
    global moved
    x0 = root.winfo_x()
    y0 = root.winfo_y()
    app.canvas.event_generate("<Button-1>", x=100, y=100)
    root.update()
    app.canvas.event_generate("<B1-Motion>", x=100, y=100)
    root.update()
    app.canvas.event_generate("<B1-Motion>", x=220, y=160)
    root.update()
    app.canvas.event_generate("<ButtonRelease-1>", x=220, y=160)
    root.update()
    moved = (root.winfo_x() != x0) or (root.winfo_y() != y0)


PLAN = [
    ("botón COMER baja hambre", click_feed, lambda: pet.hunger < 50),
    ("botón COMER anima (eating)", click_feed, lambda: app.state == "eating"),
    ("botón JUGAR sube felicidad", click_play, lambda: pet.happiness > 50),
    ("botón JUGAR anima (playing)", click_play, lambda: app.state == "playing"),
    ("botón BAÑO sube higiene", click_bathe, lambda: pet.hygiene > 50),
    ("botón DORMIR activa sueño", click_sleep_on, lambda: pet.sleeping),
    ("botón DORMIR despierta", click_sleep_off, lambda: not pet.sleeping),
    ("caca se limpia clickeando", click_poop, lambda: pet.poop == 0),
    ("drag mueve la ventana", drag_test, lambda: moved),
    ("botón CERRAR sale limpio", click_close, lambda: app.closing),
]


root.after(300, lambda: step(0))
root.mainloop()
