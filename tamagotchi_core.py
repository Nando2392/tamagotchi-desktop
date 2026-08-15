# tamagotchi_core.py
# Lógica pura del Tamagotchi de escritorio. Sin dependencias de UI.
import json
import os
import random
import time

APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
SAVE_DIR = os.path.join(APPDATA, "TamagotchiDesktop")
SAVE_PATH = os.path.join(SAVE_DIR, "save.json")

# --- Constantes de balance (por segundo, multiplicadas por la etapa) ---
RATES = {
    "hunger": 0.30,      # sube con el tiempo
    "happiness": 0.22,   # baja con el tiempo
    "hygiene": 0.16,     # baja con el tiempo
    "energy": 0.35,      # baja despierto
    "sleep_energy": 1.40,# sube durmiendo
    "sleep_hunger": 0.08,# sube más lento durmiendo
    "sleep_happiness": 0.05,
}
STAGE_MULT = {"egg": 0.0, "baby": 1.0, "child": 1.15, "teen": 1.3, "adult": 1.5}
EVOLVE_MIN = {"egg": 0.5, "baby": 3.0, "child": 8.0, "teen": 16.0}  # minutos de edad
SICK_DEATH_SEC = 75.0     # muere tras 75s enfermo
OFFLINE_CAP_SEC = 8 * 3600  # como mucho 8h de decaimiento offline

ACTION_EFFECTS = {
    "feed":    {"hunger": -38, "happiness": +6,  "hygiene": -4,  "energy": -2},
    "play":    {"happiness": +28, "energy": -12, "hunger": +6},
    "bathe":   {"hygiene": +45, "happiness": +5},
    "medicate": {"happiness": -5, "hygiene": -5},
    "clean":   {"hygiene": +10, "happiness": +3},
}
CARE_WEIGHT = {"feed": 1.2, "play": 1.0, "bathe": 1.0, "medicate": 1.5, "clean": 0.8}


class Tamagotchi:
    STAGE_ORDER = ["egg", "baby", "child", "teen", "adult"]

    def __init__(self):
        self.reset()

    # ---------------------------------------------------------------- estado
    def reset(self):
        self.stage = "egg"
        self.quality = "good"          # good | bad (forma adulta)
        self.hunger = 40.0
        self.happiness = 70.0
        self.hygiene = 80.0
        self.energy = 90.0
        self.sick = False
        self.sick_timer = 0.0
        self.sleeping = False
        self.age_minutes = 0.0
        self.alive = True
        self.dead_reason = None
        self.poop = 0
        self._poop_next = random.uniform(70, 150)
        self.care_score = 0.0          # suma ponderada de calidad de cuidados
        self.care_events = 0
        self.care_window = 0.0         # acumulado desde la última evolución
        self.created_at = time.time()
        self.last_tick = time.time()
        self.last_save = time.time()
        self._food_bonus = 0.0
        self._play_bonus = 0.0
        self._bath_bonus = 0.0
        self._forced_sleep = 0.0       # se durmió solo por agotamiento

    @property
    def stage_idx(self):
        return self.STAGE_ORDER.index(self.stage)

    @property
    def stage_name(self):
        names = {"egg": "Huevo", "baby": "Bebé", "child": "Niño",
                 "teen": "Adolescente", "adult": "Adulto"}
        return names[self.stage]

    def care_ratio(self):
        if self.care_events <= 0:
            return 0.5
        return max(0.0, min(1.0, self.care_window / self.care_events))

    # ------------------------------------------------------------- acciones
    def _record_care(self, action):
        """Registra qué tan bien quedó la mascota tras la acción (0..1)."""
        quality = 1.0
        if action == "feed":
            quality = max(0.0, 1.0 - self.hunger / 100.0)
        elif action == "play":
            quality = max(0.0, self.happiness / 100.0)
        elif action == "bathe":
            quality = max(0.0, self.hygiene / 100.0)
        elif action == "medicate":
            quality = 1.0
        elif action == "clean":
            quality = max(0.0, self.hygiene / 100.0)
        w = CARE_WEIGHT[action]
        self.care_score += quality * w
        self.care_window += quality * w
        self.care_events += int(w * 10) / 10.0

    def feed(self):
        """Devuelve (ok, mensaje)."""
        if not self.alive or self.stage == "egg":
            return False, "egg"
        if self.sleeping:
            self.sleeping = False
        for k, v in ACTION_EFFECTS["feed"].items():
            setattr(self, k, max(0.0, min(100.0, getattr(self, k) + v)))
        self._food_bonus = 2.5          # segundos de animación
        self._record_care("feed")
        self._recheck_sickness()
        return True, "feed"

    def play(self):
        if not self.alive or self.stage == "egg":
            return False, "egg"
        if self.sick:
            return False, "sick"
        if self.sleeping:
            self.sleeping = False
        if self.energy < 12:
            return False, "tired"
        for k, v in ACTION_EFFECTS["play"].items():
            setattr(self, k, max(0.0, min(100.0, getattr(self, k) + v)))
        self._play_bonus = 2.5
        self._record_care("play")
        return True, "play"

    def bathe(self):
        if not self.alive or self.stage == "egg":
            return False, "egg"
        if self.sleeping:
            self.sleeping = False
        for k, v in ACTION_EFFECTS["bathe"].items():
            setattr(self, k, max(0.0, min(100.0, getattr(self, k) + v)))
        self._bath_bonus = 2.5
        self._record_care("bathe")
        self._recheck_sickness()
        return True, "bathe"

    def medicate(self):
        if not self.alive or not self.sick:
            return False, "not_sick"
        if self.sleeping:
            self.sleeping = False
        for k, v in ACTION_EFFECTS["medicate"].items():
            setattr(self, k, max(0.0, min(100.0, getattr(self, k) + v)))
        self.sick = False
        self.sick_timer = 0.0
        self._record_care("medicate")
        return True, "medicate"

    def toggle_sleep(self):
        if not self.alive or self.stage == "egg":
            return False, "egg"
        if self.sick:
            return False, "sick"       # un pet enfermo no puede dormir
        self.sleeping = not self.sleeping
        self._forced_sleep = 0.0
        return True, "sleep" if self.sleeping else "wake"

    def clean_poop(self):
        if self.poop <= 0:
            return False, "no_poop"
        self.poop -= 1
        for k, v in ACTION_EFFECTS["clean"].items():
            setattr(self, k, max(0.0, min(100.0, getattr(self, k) + v)))
        self._record_care("clean")
        return True, "clean"

    # ------------------------------------------------------------- progreso
    def tick(self, dt):
        """Avanza el reloj interno dt segundos. Devuelve eventos para la UI."""
        if not self.alive:
            return []
        events = []
        self.last_tick = time.time()
        self.age_minutes += dt / 60.0
        if self.stage == "egg":
            if self.age_minutes >= EVOLVE_MIN["egg"]:
                self._evolve()
                events.append("hatch")
            return events

        mult = STAGE_MULT[self.stage]
        r = RATES
        # decaimiento
        if self.sleeping:
            self.hunger = min(100.0, self.hunger + r["sleep_hunger"] * dt)
            self.happiness = max(0.0, self.happiness - r["sleep_happiness"] * dt)
            self.energy = min(100.0, self.energy + r["sleep_energy"] * dt)
            if self.energy >= 100.0:
                self.sleeping = False
                events.append("woke")
        else:
            self.hunger = min(100.0, self.hunger + r["hunger"] * mult * dt)
            self.happiness = max(0.0, self.happiness - r["happiness"] * mult * dt)
            self.hygiene = max(0.0, self.hygiene - r["hygiene"] * mult * dt)
            self.energy = max(0.0, self.energy - r["energy"] * mult * dt)
            if self.energy <= 0.0:
                self.sleeping = True      # se desploma de cansancio
                self._forced_sleep = 10.0
                events.append("collapse")

        # caca periódica (solo despierto y sano)
        self._poop_next -= dt
        if (not self.sleeping and not self.sick and self.poop < 3
                and self._poop_next <= 0):
            self.poop += 1
            self._poop_next = random.uniform(70, 150)
            events.append("poop")
        # la caca ensucia más rápido
        if self.poop > 0:
            self.hygiene = max(0.0, self.hygiene - 0.08 * self.poop * dt)
            self.happiness = max(0.0, self.happiness - 0.02 * self.poop * dt)

        # enfermedad y muerte
        self._recheck_sickness()
        if self.sick:
            self.sick_timer += dt
            self.happiness = max(0.0, self.happiness - 0.3 * dt)
            if self.sick_timer >= SICK_DEATH_SEC:
                self._die("Se enfermó y nadie la curó a tiempo")
                events.append("death")
        else:
            self.sick_timer = 0.0

        # animaciones decayendo
        self._food_bonus = max(0.0, self._food_bonus - dt)
        self._play_bonus = max(0.0, self._play_bonus - dt)
        self._bath_bonus = max(0.0, self._bath_bonus - dt)
        self._forced_sleep = max(0.0, self._forced_sleep - dt)

        # evolución
        for stage, mins in EVOLVE_MIN.items():
            if self.stage == stage and self.age_minutes >= mins:
                self._evolve()
                events.append("evolve")
        return events

    def _recheck_sickness(self):
        if not self.alive:
            return
        bad = self.hunger >= 100.0 or self.hygiene <= 0.0 or self.poop >= 3
        if bad:
            if not self.sick:
                self.sick = True
                self.sick_timer = 0.0
                self.sleeping = False
        elif self.sick and self.hunger < 80.0 and self.hygiene > 20.0 and self.poop < 3:
            self.sick = False
            self.sick_timer = 0.0

    def _evolve(self):
        order = self.STAGE_ORDER
        nxt = order[min(order.index(self.stage) + 1, len(order) - 1)]
        if nxt == "adult":
            self.quality = "good" if self.care_ratio() >= 0.55 else "bad"
        self.stage = nxt
        self.care_window = 0.0
        self.care_events = 0
        self.sick = False
        self.sick_timer = 0.0

    def _die(self, reason):
        self.alive = False
        self.dead_reason = reason
        self.sleeping = False
        self.sick = False

    def needs_medication(self):
        return self.sick

    # ---------------------------------------------------------- persistencia
    def to_dict(self):
        return {
            "stage": self.stage, "quality": self.quality,
            "hunger": self.hunger, "happiness": self.happiness,
            "hygiene": self.hygiene, "energy": self.energy,
            "sick": self.sick, "sick_timer": self.sick_timer,
            "sleeping": self.sleeping, "age_minutes": self.age_minutes,
            "alive": self.alive, "dead_reason": self.dead_reason,
            "poop": self.poop, "care_score": self.care_score,
            "care_events": self.care_events,
            "created_at": self.created_at, "last_tick": self.last_tick,
        }

    @classmethod
    def from_dict(cls, d):
        t = cls()
        for k, v in d.items():
            if hasattr(t, k):
                setattr(t, k, v)
        t.care_window = 0.0
        return t

    def save(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            tmp = SAVE_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False)
            os.replace(tmp, SAVE_PATH)
            self.last_save = time.time()
            return True
        except Exception:
            return False

    @classmethod
    def load(cls):
        """Carga el estado; aplica decaimiento offline (máx 8h)."""
        try:
            with open(SAVE_PATH, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return None
        t = cls.from_dict(d)
        if t.alive:
            elapsed = min(max(0.0, time.time() - t.last_tick), OFFLINE_CAP_SEC)
            if elapsed > 5:
                # simula el paso del tiempo fuera de línea
                step = 60.0
                while elapsed > 0 and t.alive:
                    t.tick(min(step, elapsed))
                    elapsed -= step
        return t
