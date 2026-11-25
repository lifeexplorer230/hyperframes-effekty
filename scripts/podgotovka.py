#!/usr/bin/env python3
"""Подготовка ассетов клипа для библиотеки эффектов (один раз на клип). Запускать из папки проекта.

  model     - скачать модель лица YuNet (OpenCV Zoo, MIT) → modeli/face_detection_yunet_2023mar.onnx
  lico      - рамка лица раз в 0,2 с → assets/lico.json (прицел, каракули, зумы, нора встают по лицу)
  plita     - чистый фон без человека (inpaint по маске из klip-alpha.webm) → assets/plita.jpg (для «вертиго»)
  tochki    - точечный (halftone) портрет человека на чёрном, кусок клипа → assets/tochki-<t>.mp4
  oblozhki  - 8 «обложек» из кадров вашего же клипа → assets/oblozhki/o1..o8.jpg (орбита, веер, профиль, отъезд)
  mir       - карта стран world-atlas (ISC, данные Natural Earth) → assets/countries-50m.json (для «планеты»)

Запуск: python3 podgotovka.py lico | plita | tochki --t 14.0 --d 1.2 | oblozhki | model | mir  [--papka путь/к/проекту]
Человек вырезается заранее: npx --yes hyperframes@0.9.88 remove-background assets/klip.mp4 -o assets/klip-alpha.webm
"""
import argparse, json, subprocess, sys, urllib.request
from pathlib import Path

P = Path.cwd()   # папка проекта (меняется --papka)
YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")
MIR_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json"


def puti():
    A = P / "assets"
    return A, A / "klip.mp4", A / "klip-alpha.webm", P / "modeli" / "face_detection_yunet_2023mar.onnx"


def cv():
    try:
        import cv2, numpy as np
        return cv2, np
    except ImportError:
        sys.exit("нужен OpenCV: python3 -m pip install opencv-python numpy")


def dlina(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True, check=True).stdout)


def kadry(path, fps, t0=0.0, d=None, w=1080, h=1920, alpha=False):
    """Кадры через ffmpeg (rgba для webm с альфой: декодер libvpx-vp9 обязателен)."""
    _, np = cv()
    cmd = ["ffmpeg", "-loglevel", "error"]
    if alpha:
        cmd += ["-c:v", "libvpx-vp9"]
    cmd += ["-ss", str(t0), "-i", str(path)]
    if d:
        cmd += ["-t", str(d)]
    pf = "rgba" if alpha else "bgr24"
    cmd += ["-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", pf, "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * (4 if alpha else 3)
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, 4 if alpha else 3)


def skachat(url, kuda):
    kuda.parent.mkdir(parents=True, exist_ok=True)
    print("качаю", url)
    urllib.request.urlretrieve(url, kuda)
    print("готово:", kuda.relative_to(P), kuda.stat().st_size, "байт")


def model():
    *_, Y = puti()
    if Y.exists():
        print("модель уже есть:", Y.relative_to(P)); return
    skachat(YUNET_URL, Y)


def mir():
    A, *_ = puti()
    skachat(MIR_URL, A / "countries-50m.json")


def lico():
    cv2, np = cv()
    A, KLIP, _, Y = puti()
    if not Y.exists():
        model()
    det = cv2.FaceDetectorYN.create(str(Y), "", (540, 960), 0.6)
    out = []
    for i, fr in enumerate(kadry(KLIP, 5)):
        sm = cv2.resize(fr, (540, 960))
        _, f = det.detect(sm)
        if f is not None and len(f):
            x, y, w, h = (f[0][:4] * 2).tolist()
            out.append({"t": round(i * 0.2, 2), "x": round(x), "y": round(y), "w": round(w), "h": round(h)})
    if not out:
        sys.exit("лицо не найдено ни в одном кадре: нужен клип, где лицо видно анфас")
    (A / "lico.json").write_text(json.dumps(out))
    xs = [o["x"] + o["w"] / 2 for o in out]; ys = [o["y"] + o["h"] / 2 for o in out]
    print(f"лицо: {len(out)} кадров, центр x {min(xs):.0f}–{max(xs):.0f}, y {min(ys):.0f}–{max(ys):.0f}, "
          f"ширина ~{np.median([o['w'] for o in out]):.0f}")


def plita(t=5.0):
    cv2, np = cv()
    A, KLIP, ALFA, _ = puti()
    fr = next(kadry(KLIP, 1, t)); al = next(kadry(ALFA, 1, t, alpha=True))
    mask = (al[:, :, 3] > 20).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((41, 41), np.uint8))
    sm = cv2.resize(fr, (540, 960)); mk = cv2.resize(mask, (540, 960))
    res = cv2.inpaint(sm, mk, 9, cv2.INPAINT_TELEA)
    res = cv2.resize(res, (1080, 1920), interpolation=cv2.INTER_CUBIC)
    mb = cv2.GaussianBlur(mask, (61, 61), 0)[:, :, None] / 255.0
    out = (fr * (1 - mb) + cv2.GaussianBlur(res, (31, 31), 0) * mb).astype(np.uint8)
    cv2.imwrite(str(A / "plita.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("assets/plita.jpg готова")


def tochki(t0, d, cvet=(87, 119, 217), shag=22):
    """Halftone: сетка точек, радиус ~ яркость человека, фон чёрный. cvet - BGR (по умолчанию #D97757)."""
    cv2, np = cv()
    A, KLIP, ALFA, _ = puti()
    name = A / f"tochki-{t0:.2f}.mp4"
    w, h = 1080, 1920
    enc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                            "-r", "25", "-i", "-", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(name)],
                           stdin=subprocess.PIPE)
    for fr, al in zip(kadry(KLIP, 25, t0, d), kadry(ALFA, 25, t0, d, alpha=True)):
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        a = al[:, :, 3].astype(np.float32) / 255.0
        g = cv2.resize(g * a, (w // shag, h // shag), interpolation=cv2.INTER_AREA)
        g = np.clip((g - 0.05) * 1.5, 0, 1) ** 0.8
        can = np.zeros((h, w, 3), np.uint8)
        for j in range(g.shape[0]):
            for i in range(g.shape[1]):
                r = g[j, i] * shag * 0.55
                if r > 1.2:
                    cv2.circle(can, (i * shag + shag // 2, j * shag + shag // 2), int(round(r)), cvet, -1, cv2.LINE_AA)
        enc.stdin.write(can.tobytes())
    enc.stdin.close(); enc.wait()
    print(name.relative_to(P), "готов")


def oblozhki(n=8):
    """Кадры вашего клипа с разной цветокоррекцией - нейтральные «обложки», пока нет своих. Свои - просто положите
    o1.jpg…o8.jpg (9:16) в assets/oblozhki/ поверх этих."""
    A, KLIP, *_ = puti()
    (A / "oblozhki").mkdir(parents=True, exist_ok=True)
    L = dlina(KLIP)
    tona = ["eq=saturation=1.4", "hue=h=40", "eq=contrast=1.3:brightness=0.05", "hue=s=0", "hue=h=-50:s=1.3",
            "eq=gamma=1.3", "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131", "hue=h=160"]
    for k in range(n):
        t = L * (k + 0.5) / n
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(KLIP), "-frames:v", "1",
                        "-vf", f"scale=540:960:force_original_aspect_ratio=increase,crop=540:960,{tona[k % len(tona)]}",
                        "-q:v", "3", str(A / "oblozhki" / f"o{k + 1}.jpg")], check=True)
    print(f"assets/oblozhki/o1..o{n}.jpg готовы")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("chto", choices=["model", "lico", "plita", "tochki", "oblozhki", "mir"])
    ap.add_argument("--t", type=float, default=None, help="tochki: начало куска, с; plita: кадр для чистого фона")
    ap.add_argument("--d", type=float, default=1.2)
    ap.add_argument("--papka", default=None, help="папка проекта с assets/ (по умолчанию - текущая)")
    a = ap.parse_args()
    if a.papka:
        P = Path(a.papka).resolve()
    {"model": model, "lico": lico, "plita": lambda: plita(5.0 if a.t is None else a.t),
     "tochki": lambda: tochki(a.t or 0.0, a.d), "oblozhki": oblozhki, "mir": mir}[a.chto]()
