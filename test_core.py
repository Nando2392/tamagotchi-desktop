# test_core.py — pruebas rápidas de la lógica del Tamagotchi (sin UI)
import os
import sys

# fuerza un directorio de guardado temporal para no tocar el real
os.environ["APPDATA"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_testdata")

import tamagotchi_core as core  # noqa: E402

core.SAVE_DIR = os.path.join(os.environ["APPDATA"], "TamagotchiDesktop")
core.SAVE_PATH = os.path.join(core.SAVE_DIR, "save.json")

FAILS = []


def check(name, cond):
    if cond:
        print(f"  ok  {name}")
    else:
        FAILS.append(name)
        print(f"FAIL  {name}")


# 1. ciclo de vida básico
t = core.Tamagotchi()
check("empieza como huevo", t.stage == "egg" and t.alive)
t.tick(31)  # 0.5 min -> eclosiona
check("eclosiona tras ~30s", t.stage == "baby")
t.tick(5)  # el tick de eclosión no aplica decaimiento; el siguiente sí
check("bebe: hambre crece", t.hunger > 40.0)
check("bebe: felicidad baja", t.happiness < 70.0)

# 2. alimentar
t.hunger = 90
ok, _ = t.feed()
check("comer baja hambre", ok and t.hunger < 60)

# 3. jugar: con energía baja se niega
t2 = core.Tamagotchi()
t2.stage = "baby"
t2.energy = 5
ok, why = t2.play()
check("no puede jugar agotado", not ok and why == "tired")
t2.energy = 50
ok, _ = t2.play()
check("puede jugar con energía", ok and t2.happiness > 70.0)

# 4. enfermedad -> muerte por abandono
t3 = core.Tamagotchi()
t3.stage = "teen"
t3.hunger = 100
t3.tick(1)
check("hambre 100 enferma", t3.sick)
t3.tick(core.SICK_DEATH_SEC + 5)
check("muere tras 75s enfermo", not t3.alive and t3.dead_reason is not None)

# 5. medicar cura
t4 = core.Tamagotchi()
t4.stage = "teen"
t4.hunger = 100
t4.tick(1)
check("enfermo otra vez", t4.sick)
ok, _ = t4.medicate()
check("medicina cura", ok and not t4.sick)

# 6. evolución con calidad: buenos cuidados -> good, malos -> bad
t5 = core.Tamagotchi()
t5.stage = "child"
t5.age_minutes = 8.0
for _ in range(12):
    t5.feed()
t5._evolve()
check("buen cuidado -> adulto good", t5.quality == "good")

t6 = core.Tamagotchi()
t6.stage = "child"
t6.age_minutes = 8.0
for _ in range(12):
    t6.hunger = 99
    t6.tick(1)  # sin alimentar, sin limpiar -> cuidado malo
t6._evolve()
check("mal cuidado -> adulto bad", t6.quality == "bad")

# 7. caca y limpieza
t7 = core.Tamagotchi()
t7.stage = "baby"
t7._poop_next = 0.1
t7.tick(1)
check("hace caca", t7.poop >= 1)
h_before = t7.hygiene
ok, _ = t7.clean_poop()
check("limpiar caca sube higiene", ok and t7.hygiene > h_before)

# 8. sueño recarga energía
t8 = core.Tamagotchi()
t8.stage = "baby"
t8.energy = 20
t8.toggle_sleep()
t8.tick(60)
check("dormir recupera energía", t8.energy > 90)
check("se despierta solo a 100", t8.energy >= 100 and not t8.sleeping)

# 9. guardar / cargar
t9 = core.Tamagotchi()
t9.stage = "teen"
t9.hunger = 55.5
t9.save()
t9b = core.Tamagotchi.load()
check("persistencia: carga estado", t9b is not None and abs(t9b.hunger - 55.5) < 1e-6)

# 10. el pet enfermo no puede dormir
t10 = core.Tamagotchi()
t10.stage = "baby"
t10.hunger = 100
t10.tick(1)
ok, _ = t10.toggle_sleep()
check("enfermo no duerme", not ok)

# 11. dormir ralentiza el hambre
t11 = core.Tamagotchi()
t11.stage = "baby"
t11.hunger = 40
t11.toggle_sleep()
t11.tick(60)
check("durmiendo el hambre sube lento", t11.hunger < 55)

print()
if FAILS:
    print(f"{len(FAILS)} FALLOS: {FAILS}")
    sys.exit(1)
print("TODOS LOS TESTS PASAN")
