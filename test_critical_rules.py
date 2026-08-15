# test_critical_rules.py — Tests deterministas de las transiciones críticas del
# core, espejo de los escenarios de fallo del benchmark Auto Research:
#   - v3-critical-energy-over-low-health
#   - v3-compound-risk-health
#   - v3-compound-no-health-critical
# Regla P0 del reporte: la selección de acciones críticas debe ser determinista
# en código (sin delegar a un LLM) — estos tests fijan esas transiciones.
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="tama_crit_")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tamagotchi_core as core

fails = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        fails.append(name)


def make_pet(stage="baby", age=2.0, **kw):
    # edad por debajo del umbral de evolución de la etapa para que el tick
    # no evolucione a mitad del test (evolucionar cura la enfermedad)
    t = core.Tamagotchi()
    t.stage = stage
    t.age_minutes = age
    for k, v in kw.items():
        setattr(t, k, v)
    return t


# --- v3-critical-energy-over-low-health: colapso y recuperación ---
t = make_pet(energy=1.0)
t.tick(5.0)                      # 1.0 - 0.35*1.0*5 < 0 -> colapso
check("colapso por energía: se duerme solo", t.sleeping)
check("colapso fuerza sueño forzado", t._forced_sleep > 0)
t.tick(2.0)                      # durmiendo recupera 1.4/s
check("durmiendo recupera energía", t.energy > 0)

t2 = make_pet(energy=11.0)
ok, msg = t2.play()
check("jugar con energía <12 se rechaza (tired)", ok is False and msg == "tired")
t2.feed()
check("comer con energía baja sí se permite", t2.hunger < 100)

# --- v3-compound-risk-health: enfermedad por estados compuestos ---
t3 = make_pet(hunger=99.0, happiness=50.0, hygiene=60.0, energy=60.0)
t3.tick(4.0)                     # hunger 99 + 0.30*1.0*4 = 100.2 -> 100 -> enferma
check("hambre 100 enferma", t3.sick)
check("enferma no puede dormir", t3.toggle_sleep()[0] is False)
t3.medicate()
check("medicina cura", not t3.sick)

t4 = make_pet(hygiene=0.0)
t4.tick(0.1)                     # higiene <= 0 -> enferma
check("higiene 0 enferma", t4.sick)
t4.bathe()
check("baño (higiene +45) cura", not t4.sick)

t5 = make_pet(poop=3)
t5.tick(0.1)
check("3 cacas enferman", t5.sick)
t5.clean_poop(); t5.clean_poop(); t5.clean_poop()
t5.tick(0.1)                     # el recheck corre en tick
check("limpiar las cacas cura", not t5.sick)

# --- v3-compound-no-health-critical: no muerte sin enfermedad grave ---
t6 = make_pet(hunger=85.0, hygiene=30.0, happiness=10.0, energy=5.0)
t6.tick(10.0)
check("estado malo pero sin enfermedad: no muere", t6.alive)
check("estado malo pero sin enfermedad: no sick", not t6.sick)

# --- muerte si nadie cura dentro del timer (adulto: no evoluciona) ---
t7 = make_pet(stage="adult", age=99.0, hunger=100.0)
t7.tick(0.1)
check("enferma de hambre", t7.sick)
t7.tick(core.SICK_DEATH_SEC + 1.0)
check("muere tras 75s enferma sin curar", not t7.alive and t7.dead_reason)

print("CRITICAL RESULT:", "OK" if not fails else f"{len(fails)} FALLOS")
sys.exit(1 if fails else 0)
