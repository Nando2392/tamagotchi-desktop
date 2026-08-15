# tamagotchi_app.py — Tamagotchi de escritorio borderless
# Ventana transparente: lo único visible es el caparazón del dispositivo.
# Arrastra con el ratón por toda la pantalla. Esc cierra (guarda).
import os
import random
import sys
import time
import tkinter as tk

from PIL import Image, ImageTk

import tamagotchi_art as art
import tamagotchi_core as core

MAGENTA_HEX = "#FF00FF"
FPS = 12
DT_FRAME = 1.0 / FPS

POS_PATH = os.path.join(core.SAVE_DIR, "pos.json")

# mensajes cortos que aparecen en pantalla (pistas / avisos)
BTN_LABELS = {
    "feed": "Comer", "play": "Jugar", "bathe": "Baño",
    "sleep": "Dormir", "sleep_on": "Despertar", "medicate": "Medicina",
    "close": "Cerrar",
}
MSGS = {
    "egg": "El huevo tiembla… ¡toca un botón!",
    "tired": "¡Está agotada, no puede jugar!",
    "sick": "¡Está enferma! Dale medicina (B)",
    "cured": "¡Curada! 💊",
    "not_sick": "Está sana, no necesita medicina",
    "no_poop": "No hay nada que limpiar",
    "evolve": "¡Evolucionó!",
    "hatch": "¡Nació!",
    "collapse": "¡Se durmió de cansancio!",
    "dead": "Se fue al cielo… 💫",
    "new": "Pulsa A para un huevo nuevo",
}


def beep(freq, ms):
    try:
        import winsound
        winsound.Beep(int(freq), int(ms))
    except Exception:
        pass


class TamagotchiApp:
    def __init__(self, root, pos=None):
        self.root = root
        self.muted = False
        self.closing = False

        self.pet = core.Tamagotchi.load()
        if self.pet is None:
            self.pet = core.Tamagotchi()
            self.pet.save()

        # estado de animación
        self.state = "idle"          # idle|eating|playing|bathing|dead
        self.state_t = 0.0
        self.phase = 0.0
        self.blink_t = random.uniform(2.0, 4.0)
        self.blinking = False
        self.particles = []          # dicts: kind,x,y,vx,vy,t,life
        self.hover = None
        self.pressed = None
        self.dragging = False
        self.drag_off = (0, 0)
        self.msg = ""
        self.msg_t = 0.0
        self.dead_phase = "ghost"    # ghost | epitaph
        self.dead_t = 0.0
        self.last_frame = time.time()
        self.last_save = time.time()
        self.hint_text = ""

        # --- ventana borderless y transparente ---
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", MAGENTA_HEX)
        try:
            root.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        x, y = pos if pos else self._load_pos()
        root.geometry(f"{art.W}x{art.H}+{int(x)}+{int(y)}")
        self.canvas = tk.Canvas(root, width=art.W, height=art.H,
                                highlightthickness=0, bg=MAGENTA_HEX)
        self.canvas.pack()
        self.photo = ImageTk.PhotoImage(
            Image.new("RGB", (art.W, art.H), (255, 0, 255)))
        self.img_id = self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        # --- eventos ---
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        root.bind("<Escape>", lambda e: self.quit())
        root.bind("<Key-m>", lambda e: self.toggle_mute())

        self.shell = art.render_shell()
        self.root.after(1000 // FPS, self.loop)

    # ------------------------------------------------------------- posición
    def _load_pos(self):
        try:
            with open(POS_PATH, encoding="utf-8") as f:
                d = json_load(f)
                return d["x"], d["y"]
        except Exception:
            return 160, 120

    def _save_pos(self):
        try:
            os.makedirs(core.SAVE_DIR, exist_ok=True)
            with open(POS_PATH, "w", encoding="utf-8") as f:
                import json
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y()}, f)
        except Exception:
            pass

    # ------------------------------------------------------------- entrada
    def _hit_button(self, x, y):
        for name, (bx, by, r) in art.BUTTONS.items():
            if (x - bx) ** 2 + (y - by) ** 2 <= (r + 6) ** 2:
                return name
        return None

    def _hit_poop(self, x, y):
        for i in range(self.pet.poop):
            sx, sy = art.POOP_SLOTS[i]
            if abs(x - sx) <= 16 and abs(y - sy) <= 16:
                return i
        return None

    def _in_rect(self, x, y, rect):
        x0, y0, x1, y1 = rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def on_motion(self, ev):
        self.hover = None
        h = self._hit_button(ev.x, ev.y)
        if h is not None:
            self.hover = h
        elif self._in_rect(ev.x, ev.y, art.CLOSE_RECT):
            self.hover = "close"
        elif self._hit_poop(ev.x, ev.y) is not None and self.pet.poop > 0:
            self.hover = "poop"

    def on_press(self, ev):
        self.pressed = None
        # cerrar
        if self._in_rect(ev.x, ev.y, art.CLOSE_RECT):
            self.pressed = "close"
            self.quit()
            return
        # botones de acción
        b = self._hit_button(ev.x, ev.y)
        if b is not None:
            self.pressed = b
            self._do_action(b)
            return
        # limpiar caca
        p = self._hit_poop(ev.x, ev.y)
        if p is not None:
            self.pressed = "poop"
            ok, _ = self.pet.clean_poop()
            if ok:
                self._burst("sparkle", 3, self.pet)
                self._flash("¡Limpio!")
            self._save()
            return
        # arrastrar la ventana
        self.dragging = True
        self.drag_off = (ev.x_root - self.root.winfo_x(),
                         ev.y_root - self.root.winfo_y())

    def on_drag(self, ev):
        if self.dragging:
            nx = ev.x_root - self.drag_off[0]
            ny = ev.y_root - self.drag_off[1]
            self.root.geometry(f"+{int(nx)}+{int(ny)}")

    def on_release(self, ev):
        self.dragging = False
        self.pressed = None

    # ------------------------------------------------------------- acciones
    def _do_action(self, btn):
        pet = self.pet
        if not pet.alive:
            if btn == "feed":           # A = nuevo huevo
                pet.reset()
                pet.save()
                self.state = "idle"
                self.dead_phase = "ghost"
                self.dead_t = 0.0
                self._burst("sparkle", 8, None)
                self._flash("¡Nuevo huevo!")
                self._sound("hatch")
            return
        if pet.stage == "egg":
            self.state = "hatching"
            self.state_t = 0.0
            self._sound("peck")
            self._flash(MSGS["egg"])
            return
        if btn == "feed":
            ok, _ = pet.feed()
            if ok:
                self.state = "eating"
                self.state_t = 0.0
                self._sound("feed")
                # la comida cae a la boca y mastica (se anima en _compose)
        elif btn == "play":
            if pet.alive and pet.sick:
                # botón Jugar se convierte en Medicina cuando está enferma
                ok, why = pet.medicate()
                if ok:
                    self.state = "healing"
                    self.state_t = 0.0
                    self._sound("cure")
                    self._burst("sparkle", 8, pet)
                    self._flash(MSGS["cured"])
                else:
                    self._sound("error")
                    self._flash(MSGS.get(why, ""))
            else:
                ok, why = pet.play()
                if ok:
                    self.state = "playing"
                    self.state_t = 0.0
                    self._sound("play")
                    self._burst("heart", 4, pet)
                else:
                    self._sound("error")
                    self._flash(MSGS.get(why, ""))
        elif btn == "bathe":
            ok, _ = pet.bathe()
            if ok:
                self.state = "bathing"
                self.state_t = 0.0
                self._sound("bath")
                self._burst("bubble", 5, pet)
        elif btn == "sleep":
            if pet.sick:
                self._sound("error")
                self._flash(MSGS["sick"])
                return
            ok, _ = pet.toggle_sleep()
            if ok:
                self._sound("sleep" if pet.sleeping else "wake")
        self._save()

    # ------------------------------------------------------------- partículas
    def _burst(self, kind, n, pet):
        # Velocidades suaves; cada acción sale DESDE el dino (no encima de él):
        #  - comida: cae desde arriba hacia la boca (la anima _compose)
        #  - corazones/burbujas: suben desde el pecho
        #  - Zzz: suben desde la cabeza al dormir
        #  - gotas: caen dentro de la mampara al bañar
        if kind == "food":
            sx, sy = 205, 150
            vx_rng, vy_rng = (0, 6), (22, 34)
            grav = 1
        elif kind in ("heart", "sparkle"):
            sx, sy = 185, 252
            vx_rng, vy_rng = (4, 10), (16, 30)
            grav = -1
        elif kind == "bubble":
            sx, sy = 185, 252
            vx_rng, vy_rng = (6, 14), (12, 24)
            grav = -1
        elif kind == "zzz":
            sx, sy = 222, 205
            vx_rng, vy_rng = (3, 7), (10, 18)
            grav = -1
        else:  # poo, sweat, etc: desde el cuerpo hacia fuera
            sx, sy = 190, 245
            vx_rng, vy_rng = (6, 14), (14, 30)
            grav = -1
        for _ in range(n):
            vx = random.uniform(*vx_rng) * random.choice((-1, 1))
            vy = random.uniform(*vy_rng) * (1 if grav == 1 else -1)
            self.particles.append({
                "kind": kind, "x": sx, "y": sy,
                "vx": vx, "vy": vy,
                "t": 0.0, "life": random.uniform(0.9, 1.8),
                "grav": grav,
            })

    def _update_particles(self, dt):
        import math
        out = []
        for p in self.particles:
            p["t"] += dt
            if p["t"] >= p["life"]:
                continue
            if p["kind"] == "fly":
                # zumbido errático
                p["vx"] += random.uniform(-50, 50) * dt
                p["vy"] += random.uniform(-50, 50) * dt
                sp = math.hypot(p["vx"], p["vy"])
                if sp > 26:
                    p["vx"] *= 26 / sp
                    p["vy"] *= 26 / sp
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
            else:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vy"] += 120 * dt * p.get("grav", -1)
            out.append(p)
        self.particles = out

    def _flash(self, text):
        self.msg = text
        self.msg_t = 2.2

    # ------------------------------------------------------------- sonido
    def toggle_mute(self):
        self.muted = not self.muted
        self._flash("🔇 Mudo" if self.muted else "🔊 Sonido")

    def _sound(self, kind):
        if self.muted:
            return
        s = {
            "feed": ((880, 70), (660, 70)),
            "play": ((660, 90), (990, 110)),
            "bath": ((500, 60), (700, 60), (500, 60)),
            "sleep": ((440, 260),),
            "wake": ((620, 110),),
            "peck": ((900, 50),),
            "error": ((180, 160),),
            "hatch": ((660, 90), (880, 90), (1100, 180)),
            "evolve": ((523, 110), (659, 110), (784, 220)),
            "sick": ((220, 220),),
            "cure": ((660, 80), (880, 80), (1100, 120)),
            "death": ((392, 260), (262, 420)),
        }.get(kind, ())
        for f, m in s:
            beep(f, m)

    # ------------------------------------------------------------- guardado
    def _save(self):
        self.pet.save()
        self.last_save = time.time()

    def quit(self):
        if self.closing:
            return
        self.closing = True
        self.pet.save()
        self._save_pos()
        self.root.destroy()

    # ------------------------------------------------------------- bucle
    def loop(self):
        if self.closing:
            return
        now = time.time()
        dt = min(0.5, max(0.0, now - self.last_frame))
        self.last_frame = now
        self.phase = (self.phase + dt * 1.4) % 1.0
        self.state_t += dt

        if not self.pet.alive:
            self._dead_update(dt)
        else:
            events = self.pet.tick(dt)
            self._handle_events(events)
            self._anim_update(dt)

        self._update_particles(dt)
        self.msg_t = max(0.0, self.msg_t - dt)

        # autoguardado cada 30s
        if now - self.last_save > 30:
            self._save()

        frame = self._compose()
        self.photo = ImageTk.PhotoImage(frame)
        self.canvas.itemconfig(self.img_id, image=self.photo)
        self.root.after(1000 // FPS, self.loop)

    def _handle_events(self, events):
        for e in events:
            if e == "hatch":
                self._sound("hatch")
                self._flash(MSGS["hatch"])
                self._burst("sparkle", 8, None)
            elif e == "evolve":
                self._sound("evolve")
                self._flash(MSGS["evolve"])
                self._burst("sparkle", 10, None)
            elif e == "poop":
                self._flash("¡Hizo caca! Límpiala")
            elif e == "collapse":
                self._flash(MSGS["collapse"])
            elif e == "woke":
                self._sound("wake")
            elif e == "death":
                self._sound("death")
                self.state = "dead"
                self.state_t = 0.0
                self.dead_phase = "ghost"
                self.dead_t = 0.0

    def _anim_update(self, dt):
        pet = self.pet
        # enfermo: gotas de sudor desde la cabeza
        if pet.sick and pet.alive and random.random() < dt * 0.6:
            self.particles.append({
                "kind": "sweat", "x": 212 + random.randint(0, 20),
                "y": 205, "vx": 0, "vy": 14, "t": 0.0, "life": 0.9, "grav": 1})
            if not self.msg:
                self._flash(MSGS["sick"])
        # sucio: moscas + rastro de olor alrededor del dino
        if pet.alive and pet.stage != "egg" and not pet.sleeping and pet.hygiene < 30:
            flies = sum(1 for p in self.particles if p["kind"] == "fly")
            if flies < 3 and random.random() < dt * 0.7:
                self.particles.append({
                    "kind": "fly",
                    "x": random.randint(148, 252), "y": random.randint(198, 292),
                    "vx": random.choice((-1, 1)) * random.uniform(4, 10),
                    "vy": random.uniform(-6, 6), "t": 0.0,
                    "life": random.uniform(2.5, 4.0), "grav": 0})
            if random.random() < dt * 0.45:
                self.particles.append({
                    "kind": "stink",
                    "x": random.randint(160, 232), "y": random.randint(238, 292),
                    "vx": random.uniform(-4, 4), "vy": random.uniform(-14, -8),
                    "t": 0.0, "life": random.uniform(1.8, 2.8), "grav": -0.3})
        # durmiendo: Zzz que suben desde la cabeza
        if pet.sleeping and random.random() < dt * 0.8:
            self.particles.append({
                "kind": "zzz", "x": 218 + random.randint(0, 16),
                "y": 200, "vx": 6, "vy": -16, "t": 0.0, "life": 1.6, "grav": -1})
        # bañándose: lluvia de gotas dentro de la mampara
        if self.state == "bathing" and random.random() < dt * 14:
            self.particles.append({
                "kind": "drop",
                "x": random.randint(165, 245), "y": 196,
                "vx": random.uniform(-3, 3), "vy": random.uniform(55, 100),
                "t": 0.0, "life": 1.4, "grav": 1})
        # parpadeo
        self.blink_t -= dt
        if self.blink_t <= 0:
            self.blinking = True
            self.blink_t = random.uniform(2.5, 4.5)
        if self.blinking:
            self.blink_t -= dt
            if self.blink_t <= -0.15:
                self.blinking = False
                self.blink_t = random.uniform(2.5, 4.5)
        # fin de animaciones de acción
        if self.state in ("eating", "playing", "bathing", "hatching", "healing"):
            if self.state_t > 2.6:
                was_bathing = self.state == "bathing"
                self.state = "idle"
                if was_bathing:
                    # al terminar el baño ya no hay moscas (el agua las ahuyentó)
                    self.particles = [p for p in self.particles
                                      if p["kind"] not in ("fly", "stink")]

    def _dead_update(self, dt):
        self.dead_t += dt
        if self.dead_t > 7.0 and self.dead_phase == "ghost":
            self.dead_phase = "epitaph"
        if random.random() < dt * 0.5:
            self.particles.append({
                "kind": "sparkle", "x": random.randint(90, 290),
                "y": random.randint(120, 260), "vx": 0, "vy": -6,
                "t": 0.0, "life": 1.2})

    # ------------------------------------------------------------- dibujo
    def _sprite_state(self):
        if not self.pet.alive:
            return "ghost"
        if self.pet.stage == "egg":
            return "peck" if self.state == "hatching" else "idle"
        if self.pet.sick:
            return "sick"
        if self.pet.sleeping:
            return "sleep"
        if self.state == "eating":
            return "eat"
        if self.state in ("playing", "bathing", "healing"):
            return "happy"
        return "blink" if self.blinking else "idle"

    def _stage_for_sprite(self):
        if not self.pet.alive:
            return "ghost"
        return self.pet.stage

    def _compose(self):
        pet = self.pet
        frame = self.shell.copy()

        # barras de estado
        strip = art.render_status_row(pet.hunger, pet.happiness, pet.hygiene, pet.energy)
        frame.paste(strip, art.STATUS_POS, strip)

        # cacas
        for i in range(pet.poop):
            sx, sy = art.POOP_SLOTS[i]
            poo = art.render_particle("poo", 0)
            frame.paste(poo, (sx - 13, sy - 13), poo)

        # sprite
        sp_state = self._sprite_state()
        stage = self._stage_for_sprite()
        sprite_phase = self.phase
        if self.state == "eating":
            sprite_phase = (self.state_t * 2.2) % 1.0   # masticado rápido
        sprite = art.render_pet(stage, pet.quality, sp_state, sprite_phase)
        if not pet.alive:
            y_off = -abs(math_sin(self.dead_t * 1.2)) * 10
        elif self.state == "playing":
            y_off = -abs(math_sin(self.state_t * 10)) * 7
        else:
            y_off = math_sin(self.phase * 6.283) * 1.5
        px = art.PET_ANCHOR[0] - sprite.width // 2
        py = art.PET_BOTTOM - sprite.height + int(y_off)
        frame.paste(sprite, (px, py), sprite)

        # mampara de ducha durante el baño (detrás de las gotas, sobre el dino)
        if self.state == "bathing" and pet.alive:
            mam = art.render_mampara()
            mx0, my0 = art.SHOWER_RECT[0], art.SHOWER_RECT[1]
            frame.paste(mam, (mx0, my0), mam)

        # comida cayendo a la boca durante "eating" (luego desaparece: se la come)
        if self.state == "eating" and pet.alive:
            prog = self.state_t / 2.6
            bx = px + int(sprite.width * 0.78)      # punta del hocico
            by = py + int(sprite.height * 0.34)
            if prog < 0.55:
                food = art.render_particle("food", 0)
                t = prog / 0.55
                fx = bx - 25 + int(t * 25)
                fy = 150 + int(t * (by - 160))
                frame.paste(food, (fx - 13, fy - 13), food)

        # partículas
        for p in self.particles:
            img = art.render_particle(p["kind"], int(p["t"] * 12))
            frame.paste(img, (int(p["x"]) - 13, int(p["y"]) - 13), img)

        # textos
        if pet.alive:
            stage_name = pet.stage_name
            age_text = art.render_age_text(f"{stage_name} · {art.format_age(pet.age_minutes)}")
        else:
            age_text = art.render_age_text("Descansa en paz")
        frame.paste(age_text, art.TEXT_AGE, age_text)

        hint = self.msg if self.msg_t > 0 else self._hover_hint()
        if hint:
            hint_img = art.render_hint(hint)
            frame.paste(hint_img, (art.TEXT_HINT[0] - 130, art.TEXT_HINT[1]), hint_img)

        # epitafio
        if not pet.alive and self.dead_phase == "epitaph":
            dark = Image.new("RGBA", (art.SCREEN[2] - art.SCREEN[0],
                                      art.SCREEN[3] - art.SCREEN[1]), (10, 10, 14, 150))
            frame.paste(dark, (art.SCREEN[0], art.SCREEN[1]), dark)
            t1 = art.render_hint(MSGS["dead"], dark=True)
            t2 = art.render_hint(MSGS["new"], dark=True)
            frame.paste(t1, (60, 190), t1)
            frame.paste(t2, (60, 214), t2)

        # hover / press en botones
        if self.hover and self.hover in art.BUTTONS:
            bx, by, r = art.BUTTONS[self.hover]
            glow = art.render_glow(bx, by, r, pressed=(self.pressed == self.hover))
            frame.paste(glow, (bx - r - 5, by - r - 5), glow)
        return frame

    def _hover_hint(self):
        if self.hover == "close":
            return BTN_LABELS["close"]
        if self.hover == "poop":
            return "Limpiar"
        if self.hover == "sleep":
            if not self.pet.alive or self.pet.stage == "egg":
                return ""
            return BTN_LABELS["sleep_on"] if self.pet.sleeping else BTN_LABELS["sleep"]
        if self.hover == "play" and self.pet.alive and self.pet.sick:
            return BTN_LABELS["medicate"]
        if self.hover in BTN_LABELS:
            if not self.pet.alive and self.hover == "feed":
                return "Nuevo huevo"
            return BTN_LABELS[self.hover]
        return ""


def math_sin(x):
    import math
    return math.sin(x)


def json_load(f):
    import json
    return json.load(f)


def main():
    pos = None
    args = sys.argv[1:]
    if "--x" in args and "--y" in args:
        try:
            pos = (int(args[args.index("--x") + 1]), int(args[args.index("--y") + 1]))
        except Exception:
            pos = None
    root = tk.Tk()
    app = TamagotchiApp(root, pos)
    root.mainloop()


if __name__ == "__main__":
    main()
