# test_ui.py — Prueba de la UI: ventana borderless + clicks sintéticos en botones
# Verifica que los botones responden y que el frame compuesto no truena.
import os
import sys
import tempfile
import time

# guardado aislado para no tocar el real
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tama_test_")

import tkinter as tk

import tamagotchi_art as art
import tamagotchi_core as core
from tamagotchi_app import TamagotchiApp, MSGS as MSGS_UI

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def click(app, x, y, root):
    ev = type("E", (), {"x": x, "y": y, "x_root": root.winfo_x() + x,
                        "y_root": root.winfo_y() + y})()
    app.on_press(ev)
    root.update()
    app.on_release(ev)
    root.update()


root = tk.Tk()
app = TamagotchiApp(root, pos=(60, 60))

# 1. ventana borderless
check("overrideredirect (sin bordes)", bool(root.overrideredirect()))
check("transparentcolor activo", root.attributes("-transparentcolor") == "#FF00FF")

# 2. mascota recién creada en huevo
check("empieza en huevo", app.pet.stage == "egg")

# 3. botón de comer sobre el huevo -> animación de picoteo, sin crash
click(app, *art.BUTTONS["feed"][:2], root)
check("comer en huevo -> hatching", app.state == "hatching")

# 4. forzamos eclosión: ponemos la mascota en baby y probamos acciones reales
app.pet.stage = "baby"
app.pet.hunger = 30.0
app.pet.happiness = 40.0
app.pet.hygiene = 20.0
app.pet.energy = 50.0
app.pet.sick = False
app.pet.sleeping = False

h0 = app.pet.hunger
click(app, *art.BUTTONS["feed"][:2], root)
check("comer baja hambre", app.pet.hunger < h0)
check("animación eating", app.state == "eating")

hap0 = app.pet.happiness
click(app, *art.BUTTONS["play"][:2], root)
check("jugar sube felicidad", app.pet.happiness > hap0)
check("animación playing", app.state == "playing")

hy0 = app.pet.hygiene
click(app, *art.BUTTONS["bathe"][:2], root)
check("bañar sube higiene", app.pet.hygiene > hy0)

click(app, *art.BUTTONS["sleep"][:2], root)
check("dormir activa", app.pet.sleeping)
click(app, *art.BUTTONS["sleep"][:2], root)
check("dormir desactiva", not app.pet.sleeping)

# 5. enferma -> el botón de jugar (B) se convierte en MEDICINA y la cura
app.pet.sick = True
app.pet.sick_timer = 5.0
click(app, *art.BUTTONS["play"][:2], root)
check("medicina cura a la enferma", not app.pet.sick)
check("animación healing", app.state == "healing")
check("aviso de curada visible",
      app.msg == MSGS_UI["cured"] or "Curada" in app.msg)
# dar medicina a una sana no hace nada (no truena)
app.pet.sick = False
click(app, *art.BUTTONS["play"][:2], root)
check("jugar normal si está sana", app.state == "playing")

# 6. caca: limpiar clickeando encima de la caca
app.pet.poop = 1
sx, sy = art.POOP_SLOTS[0]
click(app, sx, sy, root)
check("limpiar caca", app.pet.poop == 0)

# 7. compone el frame repetidas veces (simula el loop) sin excepción
for i in range(12):
    app.phase = i / 12.0
    app.pet.tick(0.1)
    app._update_particles(0.1)
    frame = app._compose()
    assert frame is not None
print("PASS loop de composición 12 frames")

# 8. muerte -> ghost + epitafio
app.pet.alive = False
app.pet.dead_reason = "hambre"
frame = app._compose()
app.dead_phase = "epitaph"
frame = app._compose()
print("PASS ghost+epitafio componen")

app.quit()  # ya destruye root

print("\nRESULTADO:", "OK" if not failures else f"{len(failures)} FALLOS")
sys.exit(1 if failures else 0)
