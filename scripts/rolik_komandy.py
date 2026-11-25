#!/usr/bin/env python3
"""Рецепт 2 - «говорю команды, ИИ монтирует» (до/после): сверху смонтированное окно, снизу оригинал,
голос говорит команды, надпись-команда встаёт вместе с голосом (слова загораются по assets/slova.json).
Сценарий - JSON (пример: primery/komandy.json рядом с навыком). Запускать из папки проекта.

  python3 rolik_komandy.py stsenariy.json      → index.html
Рендер: npx --yes hyperframes@0.9.88 render . -o render.mp4 --fps 25

Формат сценария:
  {"dlina": 27.8 (необязательно - иначе длина клипа), "zagolovok": "ИИ-монтаж", "podpis": "оригинал",
   "shagi": [{"t": 0.0, "d": 3.4, "komanda": "Текст команды", "klyuch": "слово",
              "kom": {доп. параметры komanda(): y, razmer, levo, pravo},
              "effekty": [{"imya": "top_spisok", "t": .., "d": .., "param": {...}}]}],   (t/d эффекта - по умолчанию шага)
   "prizyv": {"t": 22.8, "slovo": "МОНТАЖ", "nad": [["Хотите так же?", "#D97757"]], "podpis": "пришлю, как это сделать"}}
  Эффект "okno_kadr" - камера верхнего окна: {"imya": "okno_kadr", "t": 11.8, "param": {"sy": 640}}.
"""
import json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import biblioteka as B
import rech

if len(sys.argv) < 2:
    sys.exit(__doc__)
S = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
klip = S.get("klip", "assets/klip.mp4"); golos = S.get("golos", "assets/golos.wav")
DLINA = S.get("dlina") or float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", klip],
                                               capture_output=True, text=True, check=True).stdout)
slova = rech.zagruzit() if Path("assets/slova.json").exists() else []
FUNKCII = {k: v[0] for k, v in {**B.EFFEKTY, **B.EFFEKTY2}.items()}

r = B.Rolik(DLINA, klip=klip, alfa=S.get("alfa", "assets/klip-alpha.webm"))
if Path(golos).exists():
    r.golos(golos, 0, DLINA, fade=0.05)
B.ekran_do_posle(r, zagolovok=S.get("zagolovok", "ИИ-монтаж"), podpis=S.get("podpis", "оригинал"))

for sh in S["shagi"]:
    t, d = sh["t"], sh["d"]
    for ef in sh.get("effekty", []):
        imya, te, de, par = ef["imya"], ef.get("t", t), ef.get("d", d), ef.get("param", {})
        if imya == "okno_kadr":
            B.okno_kadr(r, te, **par)
        elif imya in FUNKCII:
            FUNKCII[imya](r, te, de, **par)
        else:
            sys.exit(f"нет эффекта {imya}; есть: okno_kadr, {', '.join(FUNKCII)}")
    if sh.get("komanda"):
        vr = rech.vremena(slova, t, len(sh["komanda"].split())) if slova else None
        B.komanda(r, t, d, sh["komanda"], klyuch=sh.get("klyuch"), vremena=vr, **sh.get("kom", {}))

P = S.get("prizyv")
if P:
    slovo = P.get("slovo", "МОНТАЖ")
    t_pechat = P.get("t_pechat") or (rech.najti(slova, slovo, P["t"]) if slova else None)
    B.prizyv_kommentariy(r, P["t"], DLINA - P["t"], slovo=slovo, stroki=tuple(P.get("stroki", ("Напишите в комментариях", "слово"))),
                         podpis=P.get("podpis", "пришлю, как это сделать"), nad=tuple(tuple(x) for x in P.get("nad", [])),
                         t_pechat=t_pechat)
r.sobrat("index.html")
print("готово: index.html | шагов", len(S["shagi"]), "| длина", round(DLINA, 2), "| слова голоса:", "да" if slova else "нет (слова появятся сами)")
