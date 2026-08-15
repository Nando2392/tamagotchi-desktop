# smoke_check.py — smoke test determinista para el bridge de Auto Research.
# Crea la app real, ejercita cada botón y compone frames; exit 0 = la app corre.
import os
import sys
import tempfile

# guardado aislado para no tocar el real
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tama_smoke_")

import tkinter as tk

import tamagotchi_art as art
from tamagotchi_app import TamagotchiApp

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

try:
    check("arranca en huevo", app.pet.stage == "egg")

    # botón comer sobre el huevo -> hatching (no truena)
    click(app, *art.BUTTONS["feed"][:2], root)
    check("comer en huevo -> hatching", app.state == "hatching")

    # etapa baby con stats sanas
    app.pet.stage = "baby"
    app.pet.hunger = 30.0
    app.pet.happiness = 40.0
    app.pet.hygiene = 20.0
    app.pet.energy = 50.0
    app.pet.sick = False
    app.pet.sleeping = False

    click(app, *art.BUTTONS["feed"][:2], root)
    check("comer", app.state == "eating")
    click(app, *art.BUTTONS["play"][:2], root)
    check("jugar", app.state == "playing")
    click(app, *art.BUTTONS["bathe"][:2], root)
    check("bañar", app.state == "bathing")
    click(app, *art.BUTTONS["sleep"][:2], root)
    check("dormir", app.pet.sleeping)
    click(app, *art.BUTTONS["sleep"][:2], root)
    check("despertar", not app.pet.sleeping)

    # enferma -> el botón central (B) da medicina
    app.pet.sick = True
    app.pet.sick_timer = 5.0
    click(app, *art.BUTTONS["play"][:2], root)
    check("medicina cura", not app.pet.sick)

    # composición de frames (loop de animación) sin excepción
    for i in range(6):
        app.phase = i / 6.0
        app.pet.tick(0.1)
        app._update_particles(0.1)
        frame = app._compose()
        check(f"frame {i} compone", frame is not None)
finally:
    app.quit()

print("SMOKE RESULT:", "OK" if not failures else f"{len(failures)} FALLOS")
sys.exit(1 if failures else 0)
