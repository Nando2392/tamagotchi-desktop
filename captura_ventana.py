# captura_ventana.py — Captura la ventana del Tamagotchi (transparente) con PrintWindow
import ctypes, ctypes.wintypes as wt, sys, time
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

PROC_NAME = "TamagotchiDesktop.exe"

def find_hwnd():
    result = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if h:
                buf = ctypes.create_unicode_buffer(256)
                size = wt.DWORD(256)
                if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    if buf.value.lower().endswith(PROC_NAME.lower()):
                        if user32.IsWindowVisible(hwnd):
                            result.append(hwnd)
                kernel32.CloseHandle(h)
        return True
    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return result

hwnds = find_hwnd()
if not hwnds:
    print("NO VENTANA ENCONTRADA")
    sys.exit(1)
hwnd = hwnds[0]
print("hwnd:", hwnd)

# geometría
rect = wt.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w, h = rect.right - rect.left, rect.bottom - rect.top
print(f"ventana: {w}x{h} en ({rect.left},{rect.top})")

# PrintWindow al bitmap
hdc_win = user32.GetWindowDC(hwnd)
hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
old = gdi32.SelectObject(hdc_mem, bmp)
ok = user32.PrintWindow(hwnd, hdc_mem, 2)  # PW_RENDERFULLCONTENT
print("PrintWindow:", "ok" if ok else "fail")

# leer píxeles
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]
bih = BITMAPINFOHEADER()
bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
bih.biWidth = w
bih.biHeight = -h
bih.biPlanes = 1
bih.biBitCount = 32
bih.biCompression = 0
buf = ctypes.create_string_buffer(w * h * 4)
got = gdi32.GetDIBits(hdc_mem, bmp, 0, h, buf, ctypes.byref(bih), 0)
print("GetDIBits:", got, "líneas")

img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
img = img.convert("RGB")

# análisis rápido de la captura
px = img.load()
colors = {}
for y in range(0, h, 4):
    for x in range(0, w, 4):
        c = px[x, y]
        colors[c] = colors.get(c, 0) + 1
top = sorted(colors.items(), key=lambda kv: -kv[1])[:8]
print("colores dominantes:")
for c, n in top:
    print(f"  #{c[0]:02x}{c[1]:02x}{c[2]:02x} x{n}")

out = "captura_exe.png"
img.save(out)
print("guardada:", out)

gdi32.SelectObject(hdc_mem, old)
gdi32.DeleteObject(bmp)
gdi32.DeleteDC(hdc_mem)
user32.ReleaseDC(hwnd, hdc_win)
