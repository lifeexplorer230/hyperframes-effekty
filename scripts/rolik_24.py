#!/usr/bin/env python3
"""Рецепт 1 - «24 эффекта, 1 клип»: хук, затем эффекты по очереди (голос называет эффект - эффект встаёт на это
слово), счётчик NN/24, панель-чек-лист, в конце призыв «напишите в комментариях слово …». Запускать из папки проекта.

  python3 rolik_24.py                          → index.html (тайминги: по assets/slova.json, если есть, иначе поровну)
  python3 rolik_24.py --tolko vertigo,orbita   → только эти эффекты (для проб), остальное - чистый клип
  python3 rolik_24.py --nachala 3.2,4.0,...    → начала эффектов вручную (секунды, по числу эффектов)
  python3 rolik_24.py --bez steklo,tochki      → выкинуть эффекты из ролика
Рендер: npx --yes hyperframes@0.9.88 render . -o render.mp4   (кусок: --start 3 --end 6)
"""
import argparse, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biblioteka import Rolik, EFFEKTY, AK, hud_spisok, hud_nazvanie, prizyv_kommentariy, khuk_plashka
import rech

PORYADOK = ["steklo", "vertigo", "orbita", "zakhvat", "vyrezka", "blestki", "slovo_za_spinoy", "cifrovoy_zum",
            "krolichya_nora", "chat_ui", "teatr_teney", "dozhd_klavish", "chek", "shtamp", "gigantskie_titry",
            "tochki", "tir_list", "stena_profilya", "krasnyy_kollazh", "veer", "karakuli", "mrachno", "otschet", "otezd"]
NUZHNA_VYREZKA = {k for k, v in EFFEKTY.items() if v[3]}


def dlina_klipa(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True, check=True).stdout)


def skl(n):
    return "эффектов" if n % 10 in (0, 5, 6, 7, 8, 9) or 11 <= n % 100 <= 14 else ("эффект" if n % 10 == 1 else "эффекта")


ap = argparse.ArgumentParser()
ap.add_argument("--klip", default="assets/klip.mp4"); ap.add_argument("--golos", default="assets/golos.wav")
ap.add_argument("--dlina", type=float, help="длина ролика, с (по умолчанию - длина клипа)")
ap.add_argument("--tolko", default=""); ap.add_argument("--bez", default="")
ap.add_argument("--nachala", default="", help="начала эффектов через запятую")
ap.add_argument("--khuk-do", type=float, default=3.0, help="конец хука, с")
ap.add_argument("--prizyv", type=float, help="начало призыва, с (по умолчанию - по слову «комментариях» или за 3,5 с до конца)")
ap.add_argument("--slovo", default="ЭФФЕКТЫ", help="кодовое слово призыва")
ap.add_argument("--bez-vyrezki", action="store_true", help="нет klip-alpha.webm: выкинуть эффекты «за спиной»")
a = ap.parse_args()

DLINA = a.dlina or dlina_klipa(a.klip)
tolko = set(filter(None, a.tolko.split(",")))
bez = set(filter(None, a.bez.split(","))) | (NUZHNA_VYREZKA if a.bez_vyrezki else set())
if not a.bez_vyrezki and not Path("assets/klip-alpha.webm").exists() and NUZHNA_VYREZKA - bez:
    sys.exit("нет assets/klip-alpha.webm (вырезка человека). Сделайте её (см. SKILL.md, шаг 2) или запустите с --bez-vyrezki")
spisok = [k for k in PORYADOK if k not in bez]
slova = rech.zagruzit() if Path("assets/slova.json").exists() else []

# --- тайминги -----------------------------------------------------------------------------------
prizyv = a.prizyv or (slova and rech.najti(slova, "комментариях", a.khuk_do)) or DLINA - 3.5
if slova and (prizyv_slovo := rech.najti(slova, "напишите", a.khuk_do)) and prizyv_slovo < prizyv:
    prizyv = prizyv_slovo   # призыв встаёт на «Напишите…», если оно перед «комментариях»
if a.nachala:
    nachala = [float(x) for x in a.nachala.split(",")]
    if len(nachala) != len(spisok):
        sys.exit(f"--nachala: {len(nachala)} чисел, а эффектов {len(spisok)}")
else:
    nachala, t = [], a.khuk_do - 0.3
    for k in spisok:   # голос называет короткое имя эффекта (EFFEKTY[k][2]) - ищем это слово по порядку
        tk = rech.najti(slova, EFFEKTY[k][2], t + 0.1) if slova else None
        if tk is not None and tk < prizyv:
            t = tk
        nachala.append(tk if tk is not None and tk < prizyv else None)
    nashlos = sum(x is not None for x in nachala)
    # не нашлись - поровну между соседями (первый - сразу после хука, последний - до призыва)
    if nachala[0] is None:
        nachala[0] = a.khuk_do
    izv = [(n, x) for n, x in enumerate(nachala) if x is not None] + [(len(spisok), prizyv)]
    for (n0, t0), (n1, t1) in zip(izv, izv[1:]):
        for n in range(n0 + 1, n1):
            nachala[n] = t0 + (t1 - t0) * (n - n0) / (n1 - n0)
    print(f"тайминги: {f'по речи, найдено {nashlos}/{len(spisok)}' if slova else 'поровну (нет assets/slova.json)'}")
nachala = sorted(nachala)
granicy = nachala + [prizyv]
okna = [(granicy[n], max(0.4, granicy[n + 1] - granicy[n]), k) for n, k in enumerate(spisok)]

# --- сборка -------------------------------------------------------------------------------------
r = Rolik(DLINA, klip=a.klip)
if Path(a.golos).exists():
    r.golos(a.golos, 0, DLINA, fade=0.05)
else:
    print(f"нет {a.golos} - ролик соберётся без звука (сделайте: ffmpeg -i {a.klip} -vn {a.golos})")
n = len(spisok)
khuk_plashka(r, 0.0, nachala[0], chislo=n, stroki=(skl(n).upper(), "В ОДНОМ КЛИПЕ"))
hud_spisok(r, [(t, d, EFFEKTY[k][2]) for t, d, k in okna], t0=nachala[0])
for nom, (t, d, k) in enumerate(okna):
    fn, _, imya, _ = EFFEKTY[k]   # на экране - короткое имя (его же говорит голос)
    if not tolko or k in tolko:
        fn(r, t, d)
    hud_nazvanie(r, t, d, nom + 1, n, imya, imya_y={"krasnyy_kollazh": 1165, "gigantskie_titry": 1120, "chat_ui": 1150}.get(k))
r.j(f'tl.to("#spis",{{opacity:0,duration:.2}},{prizyv - .1:.2f});')
t_pechat = rech.najti(slova, a.slovo, prizyv) if slova else None
prizyv_kommentariy(r, prizyv, DLINA - prizyv, slovo=a.slovo, stroki=("Напишите в комментариях", "слово"),
                   podpis="пришлю, как это повторить", t_pechat=t_pechat,
                   nad=((f"Один клип. <span style='color:{AK}'>{n} {skl(n)}.</span>", "#fff"), ("Ноль программ монтажа.", "#fff")))
r.sobrat("index.html")
print("эффектов:", n, "| в этой сборке:", len(tolko) or n, "| призыв", round(prizyv, 2), "| длина", round(DLINA, 2))
for t, d, k in okna:
    print(f"  {t:6.2f}  {d:4.2f}  {k}")
