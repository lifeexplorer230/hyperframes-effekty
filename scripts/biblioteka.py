#!/usr/bin/env python3
"""Библиотека монтажных эффектов для HyperFrames: ролик 9:16 «как в монтажке», но без монтажки.

Как пользоваться (подробно — SKILL.md рядом):

    from biblioteka import Rolik, EFFEKTY
    r = Rolik(dlina=25.6)                          # пути assets/... — от текущей папки проекта
    r.golos("assets/golos.wav", 0, 25.6)          # звук отдельно (голос клипа)
    EFFEKTY["vertigo"][0](r, t=1.2, d=1.0)         # каждый эффект — функция (r, t, d, **параметры)
    r.sobrat("index.html")

Слои (снизу вверх):  #pod (под сценой: сетка обложек «отъезда») → #scene [ #bgv клип → #behind (за человеком)
→ .osoba (куски вырезанного человека, только в окнах эффектов «за спиной») → #infront (на сцене, едет с камерой) ]
→ #overlay (экран) → #hud (счётчик, панель, название) → #top (финал).
Эффект, которому нужен человек отдельно от фона, сам вызывает r.osoba(t, d).
Все пути в HTML относительные от папки index.html (r.pref — префикс к assets/).
"""
import re, subprocess, sys
import json, math, random
from pathlib import Path

AK = "#D97757"     # акцентный цвет (меняется здесь)
FON = "#0D0E12"    # фон плашек
PLUS, MINUS, SER = "#5EC882", "#E86A6A", "#808694"
W, H = 1080, 1920
SKRIPTY = Path(__file__).resolve().parent   # папка навыка со скриптами


def narezat_alfa(alfa, t, d, baza=None):
    """Кусок альфа-видео [t, t+d] → assets/alfa/os-T-D.webm (VP9 с альфой). Возвращает относительный путь."""
    baza = Path(baza or Path.cwd())
    rel = f"assets/alfa/os-{t:.2f}-{d:.2f}.webm"
    out = baza / rel
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-c:v", "libvpx-vp9", "-ss", f"{t:.3f}", "-i", str(baza / alfa),
                        "-t", f"{d + .04:.3f}", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                        "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", "-an", str(out)], check=True)
    return rel


class Rolik:
    def __init__(s, dlina, klip="assets/klip.mp4", alfa="assets/klip-alpha.webm", lico="assets/lico.json",
                 pref="", oblozhki=None, baza=None):
        """dlina — длина ролика, с; klip/alfa/lico — пути от папки проекта; baza — папка проекта (по умолчанию текущая);
        oblozhki — картинки для «орбиты», «веера», «стены профиля», «отъезда» (по умолчанию assets/oblozhki/o1..o8.jpg)."""
        s.D, s.pref = dlina, pref
        s.klip, s.alfa = klip, alfa
        s.L = {k: [] for k in ("pod", "behind", "infront", "overlay", "hud", "top", "panel")}
        s.css, s.js, s.media, s.osoby = [], [], [], []
        s.n = 0
        s.baza = Path(baza).resolve() if baza else Path.cwd()   # папка проекта (где index.html и assets/)
        s.lico_t = json.loads((s.baza / lico).read_text()) if lico and (s.baza / lico).exists() else []
        s.skripty = []    # доп. <script src> (d3 и т. п.)
        s.split = None    # раскладка «до/после» — см. ekran_do_posle()
        s.obl = oblozhki or [f"assets/oblozhki/o{i}.jpg" for i in range(1, 9)]

    # --- служебное -------------------------------------------------------------------------------
    def p(s, path): return s.pref + path
    def uid(s, pre="e"): s.n += 1; return f"{pre}{s.n}"
    def add(s, sloy, html): s.L[sloy].append(html)
    def j(s, code): s.js.append(code)
    def okno(s, sel, t, d):
        """Элемент виден только в [t, t+d)."""
        s.j(f'tl.set("{sel}",{{autoAlpha:1}},{t:.3f}); tl.set("{sel}",{{autoAlpha:0}},{t + d:.3f});')
    def lico(s, t):
        """Рамка лица (x, y, w, h) в момент t — линейная интерполяция трека YuNet."""
        L = s.lico_t
        if not L: return (400, 560, 300, 400)
        if t <= L[0]["t"]: o = L[0]; return (o["x"], o["y"], o["w"], o["h"])
        for a, b in zip(L, L[1:]):
            if a["t"] <= t <= b["t"]:
                k = (t - a["t"]) / max(1e-6, b["t"] - a["t"])
                return tuple(a[q] + (b[q] - a[q]) * k for q in ("x", "y", "w", "h"))
        o = L[-1]; return (o["x"], o["y"], o["w"], o["h"])
    def centr(s, t):
        x, y, w, h = s.lico(t); return (x + w / 2, y + h / 2)
    def video_kopiya(s, t, d, extra_style="", cls="vk"):
        """Копия клипа в окне [t, t+d) — синхронно с основным (для «норы», «чата», карточек)."""
        return (f'<video id="{s.uid("vk")}" class="{cls}" src="{s.p(s.klip)}" muted playsinline data-start="{t:.3f}" '
                f'data-duration="{d:.3f}" data-media-start="{t:.3f}" style="{extra_style}"></video>')
    def osoba(s, t, d, filtr=None):
        """Вырезанный человек поверх слоя #behind на время эффекта. Кусок альфа-видео режется сам
        (рендер HyperFrames раскладывает альфа-видео в PNG по ~5 МБ на кадр — целиком клип не влезает)."""
        f = narezat_alfa(s.alfa, t, d, s.baza)
        st = f"filter:{filtr};" if filtr else ""
        s.osoby.append(f'<video id="{s.uid("os")}" class="osoba" src="{s.p(f)}" muted playsinline data-start="{t:.3f}" '
                       f'data-duration="{d:.3f}" data-media-start="0" style="{st}"></video>')
    def kamera(s, t, scale=1.0, x=0, y=0, rot=0, dur=0.0, ease="power2.out"):
        """Движение «камеры» (#scene). dur=0 — резкий скачок."""
        if dur <= 0:
            s.j(f'tl.set("#scene",{{scale:{scale},x:{x},y:{y},rotation:{rot}}},{t:.3f});')
        else:
            s.j(f'tl.to("#scene",{{scale:{scale},x:{x},y:{y},rotation:{rot},duration:{dur},ease:"{ease}"}},{t:.3f});')
    def golos(s, path, t, d, fade=0.12):
        s.media.append(f'<audio id="{s.uid("au")}" src="{s.p(path)}" data-start="{t}" data-duration="{d}" data-fade-out="{fade}" data-volume="1"></audio>')

    # --- сборка ----------------------------------------------------------------------------------
    def sobrat(s, out):
        cx, cy = s.centr(5)
        css = "\n".join(s.css)
        L = {k: "\n".join(v) for k, v in s.L.items()}
        okno_a = okno_b = scene_st = ""
        if s.split:  # раскладка «до/после»: сцена живёт в верхнем окне, снизу — оригинал
            sp = s.split
            okno_a = (f'<div id="paneT" style="position:absolute;left:{sp["x"]}px;top:{sp["yT"]}px;width:{sp["w"]}px;height:{sp["hT"]}px;'
                      f'overflow:hidden;border-radius:26px;z-index:1;background:#000;box-shadow:0 18px 50px rgba(0,0,0,.45)">')
            scene_st = f' style="right:auto;bottom:auto;width:{W}px;height:{H}px"'
            okno_b = (f'<div id="panel" class="layer" style="z-index:5">{"".join(s.L.get("panel", []))}</div></div>'
                      f'<div id="paneB" style="position:absolute;left:{sp["x"]}px;top:{sp["yB"]}px;width:{sp["w"]}px;height:{sp["hB"]}px;overflow:hidden;border-radius:26px;z-index:1;background:#000">'
                      f'<video id="orig" class="vk" src="{s.p(s.klip)}" muted playsinline data-start="0" data-duration="{s.D}" '
                      f'style="transform-origin:0 0;transform:translate(0px,{-sp["y0B"] * sp["k"]:.1f}px) scale({sp["k"]:.5f})"></video></div>')
        skripty = "".join(f'<script src="{u}"></script>' for u in s.skripty)
        F = s.p("assets/fonts/")
        html = f'''<!doctype html>
<html lang="ru" data-resolution="portrait"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width={W}, height={H}"/>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>{skripty}
<style>
@font-face{{font-family:LatoB;src:url({F}Lato-Black.ttf)}}
@font-face{{font-family:LatoBd;src:url({F}Lato-Bold.ttf)}}
@font-face{{font-family:Mono;src:url({F}DejaVuSansMono.ttf)}}
@font-face{{font-family:Serif;src:url({F}LiberationSerif-Regular.ttf)}}
@font-face{{font-family:SerifB;src:url({F}LiberationSerif-Bold.ttf)}}
@font-face{{font-family:Ruka;src:url({F}Caveat.ttf)}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:#000;font-family:LatoB;color:#fff}}
.layer{{position:absolute;inset:0;pointer-events:none}}
#pod{{z-index:0;background:#000}}
#scene{{position:absolute;inset:0;z-index:1;transform-origin:{cx:.0f}px {cy:.0f}px;overflow:hidden}}
#scene>video,#bgv{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
#behind{{z-index:2}} .osoba{{position:absolute;inset:0;width:100%;height:100%;z-index:3}} #infront{{z-index:4}}
#overlay{{z-index:10}} #hud{{z-index:20}} #top{{z-index:30}}
.fx{{position:absolute;opacity:0;visibility:hidden}}
.full{{position:absolute;inset:0}}
video.vk{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;object-fit:cover}}
{css}
</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{s.D}" data-width="{W}" data-height="{H}">
 <div id="pod" class="layer">{L["pod"]}</div>
 {okno_a}<div id="scene"{scene_st}>
  <video id="bgv" src="{s.p(s.klip)}" muted playsinline data-start="0" data-duration="{s.D}"></video>
  <div id="behind" class="layer">{L["behind"]}</div>
  {"".join(s.osoby)}
  <div id="infront" class="layer">{L["infront"]}</div>
 </div>{okno_b}
 <div id="overlay" class="layer">{L["overlay"]}</div>
 <div id="hud" class="layer">{L["hud"]}</div>
 <div id="top" class="layer">{L["top"]}</div>
 {"".join(s.media)}
</div>
<script>
const tl = gsap.timeline({{paused:true}});
{chr(10).join(s.js)}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script></body></html>'''
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        # проверка: все ли файлы assets/..., на которые ссылается ролик, лежат на месте
        net = sorted({m for m in re.findall(r"(assets/[^\"'()\s]+)", html) if not (s.baza / m).exists()})
        for m in net:
            print(f"ВНИМАНИЕ: нет файла {m} - эффект с ним выйдет пустым", file=sys.stderr)
        return out


# =================================================================================================
# Оформление ролика-подборки: счётчик NN/24, название эффекта, панель-чек-лист «Эффекты», финал
# =================================================================================================
def hud_spisok(r, punkty, t0=0.0, x=780, y=640, w=235, ryadov=8):
    """Панель-чек-лист: punkty = [(t, d, 'короткое имя'), ...]. Текущий — жирный, пройденные — галочка акцентом."""
    r.css.append(f'''#spis{{position:absolute;left:{x}px;top:{y}px;width:{w}px;background:#FBFAF7;border-radius:22px;
 padding:16px 16px 10px;color:#141413;box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;overflow:hidden}}
#spis h4{{font:26px LatoB;display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
#spis h4 i{{font:18px LatoB;font-style:normal;background:#141413;color:#fff;border-radius:10px;padding:3px 8px}}
#spis .okno{{height:{ryadov * 36}px;overflow:hidden;position:relative}}
#spis ul{{list-style:none;position:absolute;left:0;right:0;top:0}}
#spis li{{height:36px;display:flex;align-items:center;gap:10px;font:22px LatoBd;color:#141413;white-space:nowrap}}
#spis li b{{width:22px;height:22px;border-radius:50%;border:2.5px solid #B9BCC4;flex:none;display:flex;align-items:center;justify-content:center;font:15px LatoB;color:#fff}}''')
    li = "".join(f'<li id="sp{k}"><b>✓</b><span>{nm}</span></li>' for k, (_, _, nm) in enumerate(punkty))
    nums = "".join(f'<span id="spn{k}" style="position:absolute;opacity:0">{k + 1:02d}/{len(punkty)}</span>' for k in range(len(punkty)))
    r.add("hud", f'<div id="spis"><h4>Эффекты<i style="position:relative;min-width:66px;height:26px">{nums}</i></h4><div class="okno"><ul id="spul">{li}</ul></div></div>')
    r.j(f'tl.fromTo("#spis",{{opacity:0,x:40}},{{opacity:1,x:0,duration:.35,ease:"back.out(1.6)"}},{t0:.3f});')
    for k in range(len(punkty)):  # начальное состояние: все пустые и серые кружки
        r.j(f'tl.set("#sp{k} b",{{color:"rgba(0,0,0,0)"}},0);')
    for k, (t, d, nm) in enumerate(punkty):
        r.j(f'tl.set("#sp{k}",{{fontWeight:900}},{t:.3f}); tl.set("#sp{k} span",{{fontFamily:"LatoB"}},{t:.3f});'
            f'tl.set("#sp{k} b",{{borderColor:"#141413"}},{t:.3f});')
        r.j(f'tl.set("#spn{k}",{{opacity:1}},{t:.3f}); tl.set("#spn{k}",{{opacity:0}},{t + d:.3f});')
        sdvig = max(0, min(k - 2, len(punkty) - ryadov)) * 36
        r.j(f'tl.to("#spul",{{y:{-sdvig},duration:.25,ease:"power2.out"}},{t:.3f});')
        tk = t + d - 0.12  # галочка в конце окна
        r.j(f'tl.set("#sp{k} b",{{backgroundColor:"{AK}",borderColor:"{AK}",color:"#fff"}},{tk:.3f});'
            f'tl.fromTo("#sp{k} b",{{scale:1.5}},{{scale:1,duration:.2,immediateRender:false}},{tk:.3f});'
            f'tl.set("#sp{k} span",{{color:"#9A9DA6",fontFamily:"LatoBd"}},{tk:.3f});')
    return "#spis"


def hud_nazvanie(r, t, d, nomer, vsego, imya, y=1080, imya_y=None):
    """Счётчик «NN/24 Название» слева сверху + крупное «/название» по центру на груди."""
    i = r.uid("nz")
    yy = imya_y if imya_y is not None else y
    r.css.append('''.sch{position:absolute;left:65px;top:285px;display:flex;align-items:center;gap:14px;font:34px LatoB;
 background:rgba(13,14,18,.72);border-radius:16px;padding:8px 18px 8px 8px}
.sch b{background:#D97757;color:#fff;border-radius:11px;padding:4px 12px;font:30px LatoB}
.imya{position:absolute;left:65px;right:65px;text-align:center;font:62px LatoB;line-height:1}
.imya span{background:rgba(13,14,18,.78);border-radius:16px;padding:10px 22px;display:inline-block}''')
    r.add("hud", f'<div id="{i}s" class="fx sch"><b>{nomer:02d}/{vsego}</b>{imya[0].upper() + imya[1:]}</div>'
                 f'<div id="{i}n" class="fx imya" style="top:{yy}px"><span>/{imya}</span></div>')
    r.okno(f"#{i}s", t, d); r.okno(f"#{i}n", t, d)
    r.j(f'tl.fromTo("#{i}n span",{{scale:.6,opacity:0}},{{scale:1,opacity:1,duration:.22,ease:"back.out(2.2)",immediateRender:false}},{t:.3f});')


def final_kartochka(r, t, d, stroki=(("Один клип.", "#fff"), ("24 эффекта.", AK), ("Ноль программ монтажа.", "#fff")),
                    podpis="HyperFrames + ИИ-агент · вместо монтажёра"):
    """L3-карточка во весь экран: строки по очереди «впечатываются»."""
    i = r.uid("fin")
    r.css.append(f'''#{i}{{background:{FON};display:flex;flex-direction:column;justify-content:center;padding:0 80px}}
#{i} .s{{font:104px LatoB;line-height:1.08;letter-spacing:-1px}} #{i} .pd{{font:30px Mono;color:{SER};margin-top:48px}}''')
    r.add("top", f'<div id="{i}" class="fx full">' + "".join(f'<div class="s" style="color:{c}">{s}</div>' for s, c in stroki)
          + f'<div class="pd">{podpis}</div></div>')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}",{{opacity:0}},{{opacity:1,duration:.2,immediateRender:false}},{t:.3f});')
    r.j(f'tl.from("#{i} .s",{{scale:1.6,opacity:0,y:-30,duration:.3,ease:"back.out(1.8)",stagger:.28,transformOrigin:"0% 50%",immediateRender:false}},{t + .1:.3f});')
    r.j(f'tl.from("#{i} .pd",{{opacity:0,duration:.3,immediateRender:false}},{t + .1 + .28 * len(stroki):.3f});')


# =================================================================================================
# 24 эффекта. Подпись у всех одна: (r, t, d=1.0, **параметры). Время — секунды ролика.
# =================================================================================================
def steklo(r, t, d=1.0, chislo="24", podpis="эффекта<br>один клип", progress="Рендер", seychas="стеклянные виджеты"):
    """1. Стеклянные виджеты: матовые карточки (backdrop-filter) выплывают слева от лица."""
    i = r.uid("gl")
    r.css.append(f'''.glass{{position:absolute;background:rgba(30,32,40,.28);backdrop-filter:blur(18px) saturate(1.5);
 -webkit-backdrop-filter:blur(18px) saturate(1.5);border:1.5px solid rgba(255,255,255,.45);border-radius:28px;
 box-shadow:0 12px 40px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.5);color:#fff;padding:20px 24px}}''')
    r.add("overlay", f'''<div id="{i}" class="fx full">
 <div class="glass" style="left:65px;top:370px;width:300px"><div style="font:110px LatoB;line-height:1">{chislo}</div>
   <div style="font:30px LatoBd;opacity:.9;margin-top:6px">{podpis}</div></div>
 <div class="glass" style="left:65px;top:620px;width:300px"><div style="font:26px LatoBd"><span style="color:{MINUS}">●</span> {progress}</div>
   <div style="height:10px;border-radius:5px;background:rgba(255,255,255,.3);margin-top:14px;overflow:hidden"><div id="{i}b" style="height:100%;width:100%;background:#fff;transform-origin:left"></div></div>
   <div style="font:22px Mono;opacity:.8;margin-top:10px">1080p · <span id="{i}p">0</span>%</div></div>
 <div class="glass" style="left:65px;top:800px;width:300px;display:flex;gap:14px;align-items:center;padding:14px 18px">
   <div style="width:52px;height:52px;border-radius:14px;background:{AK};flex:none;display:flex;align-items:center;justify-content:center;font:34px LatoB">✦</div>
   <div><div style="font:18px LatoBd;opacity:.8;letter-spacing:1px">СЕЙЧАС</div><div style="font:26px LatoB">{seychas}</div></div></div>
</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i} .glass",{{y:60,scale:.8,opacity:0,filter:"blur(12px)",duration:.4,ease:"back.out(1.5)",stagger:.09,immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i}b",{{scaleX:0}},{{scaleX:.8,immediateRender:false,duration:{d - .2:.2f},ease:"power1.inOut"}},{t + .15:.3f});')
    r.j(f'(()=>{{const o={{v:0}},e=document.querySelector("#{i}p");tl.to(o,{{v:80,duration:{d - .2:.2f},ease:"power1.inOut",onUpdate:()=>{{e.textContent=Math.round(o.v)}}}},{t + .15:.3f});}})();')


def vertigo(r, t, d=1.0, sila=1.4, plita="assets/plita.jpg"):
    """2. Вертиго (долли-зум): фон за человеком «наезжает», человек стоит. Нужны alfa и plita (podgotovka.py plita)."""
    i = r.uid("vt")
    cx, cy = r.centr(t)
    r.add("behind", f'<div id="{i}" class="fx full" style="background:url({r.p(plita)}) center/cover;transform-origin:{cx:.0f}px {cy:.0f}px"></div>')
    r.okno(f"#{i}", t, d); r.osoba(t, d)
    r.j(f'tl.fromTo("#{i}",{{scale:1,filter:"blur(0px)"}},{{scale:{sila},filter:"blur(7px)",duration:{d},ease:"power1.in",immediateRender:false}},{t:.3f});')


def orbita(r, t, d=1.0, kartinki=None, rx=440, ry=120, vitkov=0.55):
    """3. Орбита: карточки-обложки летают вокруг головы — сзади уходят за человека, спереди перекрывают."""
    i = r.uid("or")
    kart = kartinki or r.obl[:6]
    cx, cy = r.centr(t)
    r.css.append(f'.{i}c{{position:absolute;left:0;top:0;width:190px;height:338px;border-radius:18px;border:4px solid #fff;'
                 f'background-size:cover;background-position:center;box-shadow:0 10px 30px rgba(0,0,0,.45)}}')
    zad = "".join(f'<div id="{i}z{k}" class="{i}c" style="background-image:url({r.p(u)})"></div>' for k, u in enumerate(kart))
    pered = "".join(f'<div id="{i}p{k}" class="{i}c" style="background-image:url({r.p(u)})"></div>' for k, u in enumerate(kart))
    r.add("behind", f'<div id="{i}Z" class="fx full">{zad}</div>')
    r.add("infront", f'<div id="{i}P" class="fx full">{pered}</div>')
    r.okno(f"#{i}Z", t, d); r.okno(f"#{i}P", t, d); r.osoba(t, d)
    n = len(kart)
    r.j(f'''(()=>{{const o={{a:0}},n={n},Z=[...Array(n)].map((_,k)=>document.querySelector("#{i}z"+k)),P=[...Array(n)].map((_,k)=>document.querySelector("#{i}p"+k));
const f=()=>{{for(let k=0;k<n;k++){{const th=o.a*Math.PI*2+k*Math.PI*2/n, s=Math.sin(th), sc=.72+.28*(s+1)/2;
const x={cx:.0f}+{rx}*Math.cos(th)-95, y={cy + 30:.0f}+{ry}*s-169 - 40*Math.cos(th);
const tr=`translate(${{x}}px,${{y}}px) scale(${{sc}}) rotate(${{-8*Math.cos(th)}}deg)`;
Z[k].style.transform=tr; P[k].style.transform=tr; Z[k].style.opacity=s<0?1:0; P[k].style.opacity=s<0?0:1;
Z[k].style.zIndex=P[k].style.zIndex=Math.round(sc*100);}}}};
f(); tl.fromTo(o,{{a:0}},{{a:{vitkov},duration:{d},ease:"none",onUpdate:f,immediateRender:false}},{t:.3f});}})();''')
    r.j(f'tl.from("#{i}Z .{i}c, #{i}P .{i}c",{{scale:0,duration:.25,ease:"back.out(2)",immediateRender:false}},{t:.3f});')


def zakhvat(r, t, d=1.0, tekst="ЦЕЛЬ ЗАХВАЧЕНА"):
    """4. Захват цели: уголки-скобки прыгают на лицо и ведут его по треку, красная метка сверху."""
    i = r.uid("lk")
    x, y, w, h = r.lico(t)
    pad = 30
    ug = lambda st: f'<i style="position:absolute;width:70px;height:70px;{st}"></i>'
    r.css.append(f'#{i} i{{border:0 solid #fff}}')
    r.add("infront", f'''<div id="{i}" class="fx" style="left:0;top:0;width:{w + 2 * pad:.0f}px;height:{h + 2 * pad:.0f}px;left:{x - pad:.0f}px;top:{y - pad:.0f}px">
 {ug("left:0;top:0;border-left-width:7px;border-top-width:7px")}{ug("right:0;top:0;border-right-width:7px;border-top-width:7px")}
 {ug("left:0;bottom:0;border-left-width:7px;border-bottom-width:7px")}{ug("right:0;bottom:0;border-right-width:7px;border-bottom-width:7px")}
 <div id="{i}m" style="position:absolute;left:50%;top:-62px;transform:translateX(-50%);background:{MINUS};color:#fff;font:26px Mono;font-weight:bold;padding:6px 14px;border-radius:6px;white-space:nowrap">{tekst}</div>
 <div style="position:absolute;left:50%;top:50%;width:26px;height:26px;margin:-13px;border:3px solid rgba(255,255,255,.8);border-radius:50%"></div>
</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}",{{scale:1.8,opacity:0}},{{scale:1,opacity:1,duration:.22,ease:"power3.out",immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i}m",{{scaleX:0}},{{scaleX:1,duration:.15,immediateRender:false}},{t + .3:.3f});')
    k = t + 0.2
    while k < t + d:
        x2, y2, *_ = r.lico(k)
        r.j(f'tl.to("#{i}",{{x:{x2 - x:.0f},y:{y2 - y:.0f},duration:.2,ease:"none"}},{k - .2:.3f});')
        k += 0.2


def vyrezka(r, t, d=1.0, shapka="Ежедневный монтаж", zagolovok="ИИ смонтировал 24 эффекта из одного клипа",
            podzag="Монтажёры в шоке: таймлайн пустой", nomer="№ 24", data="сегодня", cena="0 ₽"):
    """5. Бумажная вырезка: человек с белой обводкой «вклеен» в газетную полосу, наклейки вокруг."""
    i = r.uid("pc")
    linii = "".join(f'<div style="height:12px;margin:14px 0;background:#CFC6B2;width:{random.Random(k).randint(70, 100)}%"></div>' for k in range(26))
    r.add("behind", f'''<div id="{i}" class="fx full" style="background:#EFE8D8;color:#1E1B16">
 <div style="position:absolute;left:65px;right:65px;top:350px;text-align:center;font:84px SerifB;border-bottom:4px double #1E1B16;padding-bottom:8px">{shapka}</div>
 <div style="position:absolute;left:65px;right:65px;top:458px;font:22px Serif;display:flex;justify-content:space-between;border-bottom:2px solid #1E1B16;padding-bottom:6px"><span>{nomer}</span><span>{data}</span><span>{cena}</span></div>
 <div style="position:absolute;left:65px;width:330px;top:510px;font:44px SerifB;line-height:1.05;text-transform:uppercase">{zagolovok}</div>
 <div style="position:absolute;left:740px;width:275px;top:510px;font:30px Serif;font-style:italic;line-height:1.15">{podzag}</div>
 <div style="position:absolute;left:65px;width:300px;top:820px">{linii}</div>
 <div style="position:absolute;left:760px;width:255px;top:860px">{linii}</div>
 <div id="{i}a" style="position:absolute;left:860px;top:700px;width:110px;height:110px;border-radius:50%;background:#F2B33D;border:6px solid #fff;box-shadow:0 6px 14px rgba(0,0,0,.25)"></div>
 <div id="{i}b" style="position:absolute;left:80px;top:1150px;font:120px LatoB;color:{MINUS};text-shadow:0 0 0 #fff;-webkit-text-stroke:5px #fff">♥</div>
</div>''')
    r.okno(f"#{i}", t, d)
    r.osoba(t, d, "drop-shadow(7px 0 0 #fff) drop-shadow(-7px 0 0 #fff) drop-shadow(0 7px 0 #fff) drop-shadow(0 -7px 0 #fff) drop-shadow(0 14px 18px rgba(0,0,0,.35))")
    r.kamera(t, 1.0, rot=-1.5); r.kamera(t, 1.03, rot=1, dur=d, ease="sine.inOut"); r.kamera(t + d, 1.0, rot=0)
    r.j(f'tl.from("#{i}a, #{i}b",{{scale:0,rotation:-40,duration:.3,ease:"back.out(2.5)",stagger:.15,immediateRender:false}},{t + .15:.3f});')


def blestki(r, t, d=1.0, slovo="ГЛАВНОЕ", n=36, seed=6):
    """6. Блёстки и прожектор: кадр темнеет кругом вокруг лица, сверху золотое слово и мерцающие искры."""
    i = r.uid("gs")
    cx, cy = r.centr(t)
    rnd = random.Random(seed)
    iskry = []
    for k in range(n):
        x, y, sz = rnd.randint(70, 1000), rnd.randint(280, 1150), rnd.randint(14, 34)
        iskry.append(f'<i class="{i}i" style="left:{x}px;top:{y}px;font-size:{sz}px">✦</i>')
    r.css.append(f'''.{i}i{{position:absolute;color:#FFE7A8;text-shadow:0 0 12px #FFD36B;font-style:normal;line-height:1}}
#{i} .zl{{position:absolute;left:0;right:0;top:285px;text-align:center;font:150px SerifB;
 background:linear-gradient(180deg,#FFF3C4 0%,#F2C14E 45%,#B9821E 100%);-webkit-background-clip:text;background-clip:text;color:transparent;
 filter:drop-shadow(0 0 18px rgba(255,200,90,.55))}}''')
    r.add("overlay", f'''<div id="{i}" class="fx full">
 <div id="{i}v" class="full" style="background:radial-gradient(ellipse 330px 430px at {cx:.0f}px {cy + 60:.0f}px, rgba(0,0,0,0) 0%, rgba(0,0,0,0) 55%, rgba(0,0,0,.78) 100%)"></div>
 <div class="zl">{slovo}</div>{"".join(iskry)}</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}v",{{opacity:0}},{{opacity:1,duration:.3,immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i} .zl",{{opacity:0,scale:1.25}},{{opacity:1,scale:1,duration:.45,ease:"power3.out",immediateRender:false}},{t + .05:.3f});')
    for k in range(n):
        st = t + rnd.uniform(0, d - .35)
        r.j(f'tl.fromTo("#{i} .{i}i:nth-of-type({k + 1})",{{scale:0,rotation:0}},{{scale:1,rotation:90,duration:.18,yoyo:true,repeat:1,immediateRender:false}},{st:.3f});')
    r.j(f'tl.set("#{i} .{i}i",{{scale:0}},{t:.3f});')


def slovo_za_spinoy(r, t, d=1.0, stroki=("ВИДЕО", "ЭФФЕКТЫ"), cvet=AK, razmer=180):
    """7. Слово за спиной: огромные буквы стоят МЕЖДУ фоном и человеком (нужна alfa)."""
    i = r.uid("bw")
    r.add("behind", f'''<div id="{i}" class="fx full"><div style="position:absolute;left:0;right:0;top:300px;text-align:center;
 font:{razmer}px LatoB;line-height:.95;color:{cvet};letter-spacing:-3px;transform:scaleY(1.3);transform-origin:top;
 text-shadow:0 0 40px rgba(217,119,87,.6), 0 6px 0 rgba(0,0,0,.25)">{"<br>".join(stroki)}</div></div>''')
    r.okno(f"#{i}", t, d); r.osoba(t, d)
    r.j(f'tl.fromTo("#{i} div",{{opacity:0,y:-80}},{{opacity:1,y:0,duration:.35,ease:"back.out(1.6)",immediateRender:false}},{t:.3f});')


def cifrovoy_zum(r, t, d=1.0, stupeni=(1.25, 1.55, 1.9), tc0=6.4):
    """8. Цифровой зум: рамка видоискателя (REC, таймкод, x-кратность) и рывками наезд на лицо."""
    i = r.uid("dz")
    ug = lambda st: f'<i style="position:absolute;width:80px;height:80px;border:0 solid rgba(255,255,255,.9);{st}"></i>'
    r.add("overlay", f'''<div id="{i}" class="fx full">
 <div style="position:absolute;left:65px;top:360px;right:65px;bottom:660px">
  {ug("left:0;top:0;border-left-width:5px;border-top-width:5px")}{ug("right:0;top:0;border-right-width:5px;border-top-width:5px")}
  {ug("left:0;bottom:0;border-left-width:5px;border-bottom-width:5px")}{ug("right:0;bottom:0;border-right-width:5px;border-bottom-width:5px")}
  <div style="position:absolute;right:26px;top:26px;font:30px Mono;font-weight:bold;display:flex;align-items:center;gap:10px"><i id="{i}r" style="width:20px;height:20px;border-radius:50%;background:{MINUS};display:block"></i>REC</div>
  <div id="{i}tc" style="position:absolute;left:26px;bottom:22px;font:28px Mono;text-shadow:0 2px 6px #000">00:00:06:10</div>
  <div id="{i}x" style="position:absolute;right:26px;bottom:22px;font:30px Mono;font-weight:bold;text-shadow:0 2px 6px #000">x1.0</div>
 </div></div>''')
    r.okno(f"#{i}", t, d)
    n = len(stupeni)
    for k, s in enumerate(stupeni):
        tk = t + 0.08 + k * (d - 0.1) / n
        x, y, w, h = r.lico(tk)
        r.kamera(tk, s)
        r.j(f'tl.set("#{i}x",{{textContent:"x{s:.1f}"}},{tk:.3f});')
    r.kamera(t + d, 1.0)
    r.j(f'tl.set("#{i}x",{{textContent:"x1.0"}},{t:.3f});')
    r.j(f'tl.to("#{i}r",{{opacity:.15,duration:.2,yoyo:true,repeat:3}},{t:.3f});')
    r.j(f'(()=>{{const o={{f:0}},e=document.querySelector("#{i}tc");tl.to(o,{{f:{int(d * 25)},duration:{d},ease:"none",onUpdate:()=>{{const F=Math.round(o.f)+{int(tc0 * 25)};e.textContent="00:00:"+String(Math.floor(F/25)).padStart(2,"0")+":"+String(F%25).padStart(2,"0")}}}},{t:.3f});}})();')


def krolichya_nora(r, t, d=1.0, urovney=3, ugol=7):
    """9. нора: кадр уходит сам в себя — вложенные копии клипа с белой рамкой, каждая повёрнута."""
    i = r.uid("rh")
    cx, cy = r.centr(t)
    sl = []
    for k in range(1, urovney + 1):
        sl.append(f'<div id="{i}k{k}" class="full" style="transform-origin:{cx:.0f}px {cy:.0f}px;outline:8px solid #fff;overflow:hidden;box-shadow:0 0 40px rgba(0,0,0,.6)">{r.video_kopiya(t, d)}</div>')
    r.add("overlay", f'<div id="{i}" class="fx full">{"".join(sl)}</div>')
    r.okno(f"#{i}", t, d)
    for k in range(1, urovney + 1):
        zn = 1 if k % 2 else -1
        r.j(f'tl.fromTo("#{i}k{k}",{{scale:1,rotation:0}},{{scale:{0.74 ** k * 0.9:.3f},rotation:{ugol * 2.2 * k * zn:.1f},duration:{d:.2f},ease:"power3.out",immediateRender:false}},{t + 0.05 * k:.3f});')


def chat_ui(r, t, d=1.0, zapros="Сделай из этого рилс: 24 эффекта, без монтажа", otvet="Готово. Вот ваш рилс - смонтирован.",
            chipy=("стекло", "вертиго", "орбита", "+21"), imya="ИИ-ассистент"):
    """10. Интерфейс ИИ-чата: кадр сжимается во вложение чата, ниже запрос, ответ ассистента и чипы эффектов.
    Значок нейтральный (кружок с «ИИ»), без логотипов. Текст держится левее x 760 - справа стоит панель-чек-лист ролика."""
    i = r.uid("cu")
    k = 0.25  # масштаб карточки-видео
    cx0, cy0 = 490, 335  # левый верх карточки
    chips = "".join(f'<span style="border:2px solid {AK};color:{AK};border-radius:20px;padding:4px 14px;font:24px LatoBd">{c}</span>' for c in chipy)
    znachok = (f'<span style="width:58px;height:58px;border-radius:50%;background:{AK};color:#fff;font:26px LatoB;display:inline-flex;'
               f'align-items:center;justify-content:center;flex:none">ИИ</span>')
    r.add("overlay", f'''<div id="{i}" class="fx full" style="background:#F5F0E8;color:#1F1F1E">
 <div style="position:absolute;left:65px;top:355px;display:flex;align-items:center;gap:14px">{znachok}<span style="font:40px Serif">{imya}</span></div>
 <div id="{i}u" style="position:absolute;left:150px;width:610px;top:{cy0 + 1920 * k + 20:.0f}px;text-align:right"><span style="display:inline-block;background:#E8E0D2;border-radius:22px;padding:14px 20px;font:30px LatoBd;text-align:left;line-height:1.2">{zapros}</span></div>
 <div id="{i}a" style="position:absolute;left:65px;width:695px;top:{cy0 + 1920 * k + 150:.0f}px"><div style="font:34px Serif;line-height:1.2"><span style="color:{AK}">●</span> {otvet}</div>
   <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">{chips}</div></div>
 <div id="{i}v" style="position:absolute;left:0;top:0;width:1080px;height:1920px;transform-origin:0 0;border-radius:60px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.25)">{r.video_kopiya(t, d)}</div>
</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}v",{{x:0,y:0,scale:1}},{{x:{cx0},y:{cy0},scale:{k},duration:.45,ease:"power3.inOut",immediateRender:false}},{t:.3f});')
    r.j(f'tl.from("#{i}u",{{opacity:0,y:30,duration:.25,immediateRender:false}},{t + .35:.3f});')
    r.j(f'tl.from("#{i}a",{{opacity:0,y:30,duration:.25,immediateRender:false}},{t + .55:.3f});')


def teatr_teney(r, t, d=1.0, figury=("✂", "▶", "★")):
    """11. Театр теней: тёплый свет, на фоне за человеком проплывают размытые тени-фигуры (нужна alfa)."""
    i = r.uid("sp")
    pos = [(90, 330, 330, -12), (640, 300, 260, 8), (160, 820, 220, 20)]
    tn = "".join(f'<div class="{i}f" style="position:absolute;left:{x}px;top:{y}px;font-size:{s}px;line-height:1;color:rgba(25,12,0,.72);filter:blur(7px);transform:rotate({a}deg)">{f}</div>'
                 for f, (x, y, s, a) in zip(figury, pos))
    r.add("behind", f'''<div id="{i}" class="fx full">
 <div class="full" style="background:rgba(255,150,60,.38);mix-blend-mode:multiply"></div>
 <div class="full" style="background:radial-gradient(ellipse 600px 700px at 55% 35%, rgba(255,210,150,.35), rgba(0,0,0,.55))"></div>{tn}</div>''')
    r.okno(f"#{i}", t, d); r.osoba(t, d, "sepia(.35) saturate(1.1) brightness(.95)")
    r.j(f'tl.fromTo("#{i} .{i}f",{{x:-40}},{{x:60,duration:{d},ease:"sine.inOut",stagger:.05,immediateRender:false}},{t:.3f});')


def dozhd_klavish(r, t, d=1.0, klavishi=("Ctrl", "Z", "C", "V", "⌘", "Shift", "Alt", "Del", "Enter", "Tab", "Esc", "J", "K", "L", "S", "⌫", "F", "B", "M", "I", "O"), seed=12):
    """12. Дождь из клавиш: горячие клавиши монтажки сыплются сверху с вращением."""
    i = r.uid("kr")
    rnd = random.Random(seed)
    r.css.append(f'''.{i}k{{position:absolute;top:0;min-width:96px;height:96px;padding:0 18px;border-radius:18px;background:#F4F4F1;color:#2B2C30;
 font:34px LatoB;display:flex;align-items:center;justify-content:center;box-shadow:0 7px 0 #B9BAC0,0 14px 24px rgba(0,0,0,.35)}}''')
    ks = "".join(f'<div class="{i}k" id="{i}k{n}" style="left:{rnd.randint(40, 940)}px">{k}</div>' for n, k in enumerate(klavishi))
    r.add("overlay", f'<div id="{i}" class="fx full">{ks}</div>')
    r.okno(f"#{i}", t, d)
    for n in range(len(klavishi)):
        st = t + rnd.uniform(0, d * 0.45)
        r.j(f'tl.fromTo("#{i}k{n}",{{y:{rnd.randint(-260, -120)},rotation:{rnd.randint(-60, 60)}}},{{y:{rnd.randint(1250, 1900)},rotation:{rnd.randint(-200, 200)},duration:{rnd.uniform(.55, .8):.2f},ease:"power2.in",immediateRender:false}},{st:.3f});')
        r.j(f'tl.set("#{i}k{n}",{{y:-400}},{t:.3f});')


def chek(r, t, d=1.0, pozicii=("стекло", "вертиго", "орбита", "захват", "вырезка", "блёстки", "зум", "нора"), itogo="0 ₽"):
    """13. Чек: из «принтера» сверху выползает чек — список эффектов, у каждого 0 ₽, ИТОГО 0 ₽."""
    i = r.uid("bl")
    st = "".join(f'<div style="display:flex;justify-content:space-between"><span>{p}</span><span>0 ₽</span></div>' for p in pozicii)
    r.add("overlay", f'''<div id="{i}" class="fx" style="left:65px;top:282px;width:330px;height:640px;overflow:hidden;transform:rotate(-2deg);transform-origin:top left">
 <div style="position:absolute;left:0;top:0;width:330px;height:14px;background:#2B2C30;border-radius:7px;z-index:2"></div>
 <div id="{i}p" style="position:absolute;left:12px;right:12px;top:6px;background:#FBFAF7;color:#222;font:21px Mono;line-height:1.5;padding:18px 18px 30px;
   box-shadow:0 10px 22px rgba(0,0,0,.35);clip-path:polygon(0 0,100% 0,100% calc(100% - 12px),95% 100%,90% calc(100% - 12px),85% 100%,80% calc(100% - 12px),75% 100%,70% calc(100% - 12px),65% 100%,60% calc(100% - 12px),55% 100%,50% calc(100% - 12px),45% 100%,40% calc(100% - 12px),35% 100%,30% calc(100% - 12px),25% 100%,20% calc(100% - 12px),15% 100%,10% calc(100% - 12px),5% 100%,0 calc(100% - 12px))">
   <div style="text-align:center;font-weight:bold">МОНТАЖ · ЧЕК №24</div><div style="border-top:2px dashed #999;margin:8px 0"></div>
   {st}<div style="display:flex;justify-content:space-between"><span>часы монтажа</span><span>0</span></div>
   <div style="border-top:2px dashed #999;margin:8px 0"></div>
   <div style="display:flex;justify-content:space-between;font-size:30px;font-weight:bold"><span>ИТОГО</span><span>{itogo}</span></div>
 </div></div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}p",{{yPercent:-100}},{{yPercent:0,duration:{min(.7, d - .2):.2f},ease:"steps(9)",immediateRender:false}},{t:.3f});')


def shtamp(r, t, d=1.0, tekst="ОТКЛОНЕНО"):
    """14. Штамп «отклонено»: сверху таймлайн монтажки (дорожки), на него с размаху бьёт красный штамп."""
    i = r.uid("rs")
    cv = ["#8B6CEF", "#4C8DF6", PLUS, "#F2C14E", AK]
    rnd = random.Random(3)
    dor = ""
    for k, c in enumerate(cv):
        x = 0; bl = ""
        while x < 600:
            w = rnd.randint(60, 180); bl += f'<i style="position:absolute;left:{x}px;width:{w - 6}px;top:0;bottom:0;background:{c};border-radius:6px"></i>'; x += w
        dor += f'<div style="position:relative;height:26px;margin:8px 0">{bl}</div>'
    r.add("overlay", f'''<div id="{i}" class="fx" style="left:65px;top:345px;width:660px;height:230px;background:#1E1F24;border-radius:18px;padding:12px 30px;box-shadow:0 12px 30px rgba(0,0,0,.45);overflow:hidden">
 <div style="font:18px Mono;color:#9A9DA6;margin-bottom:4px">таймлайн · 00:24</div>{dor}
 <i style="position:absolute;left:330px;top:30px;bottom:0;width:3px;background:#fff"></i></div>
<div id="{i}s" class="fx" style="left:120px;top:395px;font:86px LatoB;color:{MINUS};border:9px solid {MINUS};border-radius:16px;padding:0 22px;transform:rotate(-12deg);
 letter-spacing:4px;mix-blend-mode:normal;text-shadow:0 0 1px {MINUS};opacity:.95">{tekst}</div>''')
    r.okno(f"#{i}", t, d); r.okno(f"#{i}s", t + .35, d - .35)
    r.j(f'tl.from("#{i}",{{y:-40,opacity:0,duration:.25,immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i}s",{{scale:2.6,opacity:0}},{{scale:1,opacity:.95,duration:.16,ease:"power4.in",immediateRender:false}},{t + .35:.3f});')
    r.j(f'tl.fromTo("#{i}",{{x:0}},{{x:8,duration:.04,yoyo:true,repeat:3,immediateRender:false}},{t + .51:.3f});')
    r.j(f'tl.set("#{i}",{{x:0}},{t + .7:.3f});')


def gigantskie_titry(r, t, d=1.0, bolshoe="КРУПНО", maloe="титры", maloe_y=1005):
    """15. Гигантские титры: огромное слово за головой (alfa) + мелкое тонкое слово с засечками спереди."""
    i = r.uid("gc")
    r.add("behind", f'<div id="{i}" class="fx full"><div style="position:absolute;left:0;right:0;top:275px;text-align:center;font:250px LatoB;color:#F5E14B;letter-spacing:-4px;transform:scaleY(1.35);transform-origin:top">{bolshoe}</div></div>')
    r.add("infront", f'<div id="{i}m" class="fx" style="left:0;right:0;top:{maloe_y}px;text-align:center;font:96px Serif;font-style:italic;color:#fff;text-shadow:0 4px 18px rgba(0,0,0,.7)">{maloe}</div>')
    r.okno(f"#{i}", t, d); r.okno(f"#{i}m", t + .15, d - .15); r.osoba(t, d)
    r.j(f'tl.fromTo("#{i} div",{{scaleY:0}},{{scaleY:1.35,duration:.25,ease:"back.out(1.6)",immediateRender:false}},{t:.3f});')
    r.j(f'tl.from("#{i}m",{{opacity:0,y:20,duration:.25,immediateRender:false}},{t + .15:.3f});')


def tochki(r, t, d=1.0, fayl=None):
    """16. Точечный портрет: человек превращается в сетку точек на чёрном (кадры готовит podgotovka.py tochki)."""
    i = r.uid("dr")
    f = fayl or f"assets/tochki-{max(0.0, t - .1):.2f}.mp4"
    if not (r.baza / f).exists():   # кадры точек готовит podgotovka.py (OpenCV), ~20 с счёта на 1 с ролика
        subprocess.run([sys.executable, str(SKRIPTY / "podgotovka.py"), "tochki", "--t", f"{max(0.0, t - .1):.2f}",
                        "--d", f"{d + .2:.2f}", "--papka", str(r.baza)], check=True)
    r.add("overlay", f'''<div id="{i}" class="fx full" style="background:#000">
 <video id="{i}v" src="{r.p(f)}" muted playsinline data-start="{t:.3f}" data-duration="{d:.3f}" data-media-start="0.1" style="position:absolute;inset:0;width:100%;height:100%"></video></div>''')
    r.okno(f"#{i}", t, d)
    cx, cy = r.centr(t)
    r.j(f'tl.fromTo("#{i}",{{clipPath:"circle(0px at {cx:.0f}px {cy:.0f}px)"}},{{clipPath:"circle(1300px at {cx:.0f}px {cy:.0f}px)",duration:.35,ease:"power2.out",immediateRender:false}},{t:.3f});')


def tir_list(r, t, d=1.0, ryady=("S", "A", "B", "C", "D"), elementy=(("ИИ-монтаж", 0), ("шаблоны", 2), ("монтажёр", 4))):
    """17. Тир-лист: панель S…D слева снизу, плашки прилетают в свои ряды."""
    i = r.uid("tl")
    cv = [MINUS, AK, "#F2C14E", PLUS, "#4C8DF6"]
    rows = "".join(f'<div style="display:flex;height:50px;margin-bottom:6px"><b style="width:50px;background:{c};border-radius:8px;display:flex;align-items:center;justify-content:center;font:30px LatoB;color:#141413">{b}</b><div id="{i}r{k}" style="flex:1;margin-left:6px;background:rgba(255,255,255,.08);border-radius:8px"></div></div>'
                   for k, (b, c) in enumerate(zip(ryady, cv)))
    el = "".join(f'<div id="{i}e{n}" style="position:absolute;left:62px;top:{14 + 56 * row:.0f}px;height:42px;padding:0 14px;background:#fff;color:#141413;border-radius:8px;font:24px LatoB;display:flex;align-items:center;white-space:nowrap">{nm}</div>'
                 for n, (nm, row) in enumerate(elementy))
    r.add("overlay", f'<div id="{i}" class="fx" style="left:65px;top:735px;width:340px;padding:10px;background:rgba(20,20,24,.9);border-radius:16px">{rows}{el}</div>')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i}",{{x:-380,duration:.25,ease:"power3.out",immediateRender:false}},{t:.3f});')
    for n in range(len(elementy)):
        r.j(f'tl.from("#{i}e{n}",{{x:420,y:-160,rotation:15,opacity:0,duration:.28,ease:"back.out(1.4)",immediateRender:false}},{t + .25 + n * .2:.3f});')


def stena_profilya(r, t, d=1.0, kartinki=None, knopka=("Подписаться", "Вы подписаны ✓")):
    """18. Стена профиля: за головой сетка обложек как в профиле, внизу кнопка «Подписаться» нажимается."""
    i = r.uid("pw")
    kart = (kartinki or r.obl)[:8]
    cw, ch = 232, 412
    plit = "".join(f'<div style="position:absolute;left:{65 + (k % 4) * (cw + 8)}px;top:{280 + (k // 4) * (ch + 8)}px;width:{cw}px;height:{ch}px;background:url({r.p(u)}) center/cover;border-radius:6px"></div>' for k, u in enumerate(kart))
    r.add("behind", f'<div id="{i}" class="fx full" style="background:#000">{plit}</div>')
    r.add("overlay", f'''<div id="{i}b" class="fx" style="left:65px;top:960px;width:300px;height:76px;border-radius:16px;background:#3D7BF7;font:32px LatoB;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 20px rgba(0,0,0,.4)">
 <span id="{i}b1">{knopka[0]}</span><span id="{i}b2" style="position:absolute;opacity:0">{knopka[1]}</span></div>''')
    r.okno(f"#{i}", t, d); r.okno(f"#{i}b", t + .2, d - .2); r.osoba(t, d)
    r.j(f'tl.from("#{i} div",{{scale:.6,opacity:0,duration:.25,ease:"back.out(1.6)",stagger:.04,immediateRender:false}},{t:.3f});')
    tk = t + .6
    r.j(f'tl.to("#{i}b",{{scale:.9,duration:.06,yoyo:true,repeat:1}},{tk:.3f}); tl.set("#{i}b",{{backgroundColor:"#2B2C30"}},{tk + .06:.3f});'
        f'tl.set("#{i}b1",{{opacity:0}},{tk + .06:.3f}); tl.set("#{i}b2",{{opacity:1}},{tk + .06:.3f});')


def krasnyy_kollazh(r, t, d=1.0, slovo="БЕСПЛАТНО", stroki=(("ОДИН КЛИП.", "#fff"), ("24 ЭФФЕКТА.", MINUS), ("НОЛЬ ПРОГРАММ.", "#fff"))):
    """19. Красный коллаж: чёрный фон, человек ч/б, за ним огромное красное слово, слева снизу три строки."""
    i = r.uid("rc")
    r.add("behind", f'<div id="{i}" class="fx full" style="background:#0A0A0A"><div style="position:absolute;left:0;right:0;top:290px;text-align:center;font:150px LatoB;color:#E32626;letter-spacing:-3px;transform:scaleY(1.7);transform-origin:top">{slovo}</div></div>')
    r.add("overlay", f'<div id="{i}t" class="fx" style="left:65px;top:1000px;font:46px LatoB;line-height:1.02;transform:scaleY(1.15);transform-origin:top left">'
          + "".join(f'<div style="color:{c};background:rgba(10,10,10,.85);display:table;padding:2px 14px;margin-bottom:6px">{s}</div>' for s, c in stroki) + '</div>')
    r.okno(f"#{i}", t, d); r.okno(f"#{i}t", t, d); r.osoba(t, d, "grayscale(1) contrast(1.25) brightness(1.05)")
    r.j(f'tl.fromTo("#{i} div",{{opacity:0,scaleY:2.4}},{{opacity:1,scaleY:1.7,duration:.2,ease:"power3.out",immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i}t div",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:.12,stagger:.12,immediateRender:false}},{t + .15:.3f});')


def veer(r, t, d=1.0, kartinki=None, ugol=62):
    """20. Веер телефонов: телефоны с обложками раскрываются веером за спиной (alfa)."""
    i = r.uid("pf")
    kart = (kartinki or r.obl)[:7]
    n = len(kart)
    cx, cy = r.centr(t)
    tel = "".join(f'<div id="{i}t{k}" style="position:absolute;left:{cx - 140:.0f}px;top:330px;width:280px;height:540px;border-radius:36px;border:10px solid #111;background:url({r.p(u)}) center/cover;transform-origin:50% 190%;box-shadow:0 14px 34px rgba(0,0,0,.5)"></div>' for k, u in enumerate(kart))
    r.add("behind", f'<div id="{i}" class="fx full">{tel}</div>')
    r.okno(f"#{i}", t, d); r.osoba(t, d)
    for k in range(n):
        a = -ugol + 2 * ugol * k / (n - 1)
        r.j(f'tl.fromTo("#{i}t{k}",{{rotation:0,y:260}},{{rotation:{a:.1f},y:0,duration:.45,ease:"back.out(1.3)",immediateRender:false}},{t + .03 * k:.3f});')


def karakuli(r, t, d=1.0, podpis="я, монтирую", cvet="#FFE066"):
    """21. Каракули: от руки обводится лицо, над головой корона, искры и стрелка с подписью."""
    i = r.uid("sc")
    x, y, w, h = r.lico(t + .3)
    cx, cy = x + w / 2, y + h / 2
    rx, ry = w * .72, h * .66
    # «рукописный» овал: две петли с дрожанием
    pts = []
    rnd = random.Random(4)
    for k in range(0, 451, 10):
        a = math.radians(k - 100)
        j = 1 + rnd.uniform(-.03, .03) + (k / 450) * .06
        pts.append(f"{cx + rx * j * math.cos(a):.0f},{cy + ry * j * math.sin(a):.0f}")
    path = "M" + " L".join(pts)
    ky = y - h * .25
    korona = f"M{cx - 95:.0f},{ky:.0f} L{cx - 110:.0f},{ky - 95:.0f} L{cx - 50:.0f},{ky - 40:.0f} L{cx:.0f},{ky - 115:.0f} L{cx + 50:.0f},{ky - 40:.0f} L{cx + 110:.0f},{ky - 95:.0f} L{cx + 95:.0f},{ky:.0f} Z"
    strelka = f"M{140:.0f},{cy + 190:.0f} Q{150:.0f},{cy + 60:.0f} {cx - rx - 10:.0f},{cy + 40:.0f}"
    r.add("infront", f'''<div id="{i}" class="fx full"><svg width="1080" height="1920" style="position:absolute;inset:0" fill="none" stroke="{cvet}" stroke-width="9" stroke-linecap="round" stroke-linejoin="round">
 <path id="{i}o" d="{path}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>
 <path id="{i}k" d="{korona}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" fill="rgba(255,224,102,0)"/>
 <path id="{i}s" d="{strelka}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" stroke-width="7"/>
 <path id="{i}s2" d="M{cx - rx - 10:.0f},{cy + 40:.0f} l-40,-6 M{cx - rx - 10:.0f},{cy + 40:.0f} l-22,34" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" stroke-width="7"/>
</svg>
<div id="{i}t" style="position:absolute;left:65px;top:{cy + 200:.0f}px;font:64px Ruka;font-weight:700;color:{cvet};transform:rotate(-8deg);text-shadow:0 2px 8px rgba(0,0,0,.5)">{podpis}</div>
<div id="{i}z1" style="position:absolute;left:{cx + rx + 20:.0f}px;top:{cy - ry:.0f}px;font:60px LatoB;color:#fff">✦</div>
<div id="{i}z2" style="position:absolute;left:{cx - rx - 90:.0f}px;top:{cy - ry - 40:.0f}px;font:44px LatoB;color:#7FE3F0">✦</div></div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.to("#{i}o",{{strokeDashoffset:0,duration:.35,ease:"power1.inOut"}},{t:.3f});')
    r.j(f'tl.to("#{i}k",{{strokeDashoffset:0,duration:.25,ease:"none"}},{t + .3:.3f}); tl.to("#{i}k",{{fill:"rgba(255,224,102,.85)",duration:.15}},{t + .55:.3f});')
    r.j(f'tl.to("#{i}s",{{strokeDashoffset:0,duration:.25}},{t + .35:.3f}); tl.to("#{i}s2",{{strokeDashoffset:0,duration:.1}},{t + .6:.3f});')
    r.j(f'tl.from("#{i}t",{{opacity:0,duration:.15,immediateRender:false}},{t + .4:.3f});')
    r.j(f'tl.from("#{i}z1, #{i}z2",{{scale:0,rotation:-90,duration:.25,ease:"back.out(3)",stagger:.1,immediateRender:false}},{t + .45:.3f});')


def mrachno(r, t, d=1.0):
    """22. Мрачный свет: кадр уходит в тень, свет остаётся только на лице (фильтр + виньетка)."""
    i = r.uid("md")
    cx, cy = r.centr(t)
    r.add("infront", f'<div id="{i}" class="fx full" style="background:radial-gradient(ellipse 260px 340px at {cx:.0f}px {cy:.0f}px, rgba(0,0,0,0) 50%, rgba(0,0,0,.8) 100%)"></div>')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}",{{opacity:0}},{{opacity:1,duration:.3,immediateRender:false}},{t:.3f});')
    r.j(f'tl.set("#bgv",{{filter:"brightness(1) contrast(1) saturate(1)"}},{t:.3f});'
        f'tl.to("#bgv",{{filter:"brightness(0.8) contrast(1.25) saturate(0.6)",duration:.3}},{t:.3f});'
        f'tl.set("#bgv",{{filter:"none"}},{t + d:.3f});')


def otschet(r, t, d=1.0, s=3, podpisi=("МИН", "СЕК")):
    """23. Обратный отсчёт: огромные цифры 00:03 → 00:01 за головой (alfa), каждая смена — вниз-вверх."""
    i = r.uid("cd")
    n = s
    cif = "".join(f'<span id="{i}c{k}" style="position:absolute;left:0;right:0;opacity:0">00:{n - k:02d}</span>' for k in range(n))
    r.add("behind", f'''<div id="{i}" class="fx full"><div style="position:absolute;left:0;right:0;top:300px;height:300px;text-align:center;font:240px LatoB;color:#fff;letter-spacing:4px;text-shadow:0 10px 30px rgba(0,0,0,.5)">{cif}</div>
 <div style="position:absolute;left:0;right:0;top:600px;display:flex;justify-content:center;gap:300px;font:30px LatoB;color:#fff;letter-spacing:6px">{"".join(f"<span>{p}</span>" for p in podpisi)}</div></div>''')
    r.okno(f"#{i}", t, d); r.osoba(t, d)
    step = d / n
    for k in range(n):
        r.j(f'tl.fromTo("#{i}c{k}",{{opacity:0,y:-60}},{{opacity:1,y:0,duration:.12,immediateRender:false}},{t + k * step:.3f});')
        if k < n - 1:
            r.j(f'tl.to("#{i}c{k}",{{opacity:0,y:60,duration:.1}},{t + (k + 1) * step - .05:.3f});')


def otezd(r, t, d=1.0, kartinki=None, masshtab=1 / 3):
    """24. Отъезд: кадр уменьшается в центр сетки ленты из 3×3 обложек (сцена встаёт в центральную ячейку)."""
    i = r.uid("pb")
    kart = (kartinki or r.obl)[:8]
    cw, ch = W / 3, H / 3
    cells, n = [], 0
    for rr in range(3):
        for cc in range(3):
            if rr == 1 and cc == 1: continue
            cells.append(f'<div style="position:absolute;left:{cc * cw + 4:.0f}px;top:{rr * ch + 4:.0f}px;width:{cw - 8:.0f}px;height:{ch - 8:.0f}px;background:url({r.p(kart[n % len(kart)])}) center/cover;border-radius:10px"></div>'); n += 1
    r.add("pod", f'<div id="{i}" class="fx full" style="background:#000">{"".join(cells)}</div>')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.set("#scene",{{transformOrigin:"540px 960px"}},{t:.3f});')
    r.j(f'tl.to("#scene",{{scale:{masshtab:.4f},borderRadius:30,duration:.55,ease:"power3.inOut"}},{t + .05:.3f});')
    r.j(f'tl.set("#scene",{{scale:1,borderRadius:0,clearProps:"transformOrigin"}},{t + d:.3f});')
    r.j(f'tl.from("#{i} div",{{opacity:0,scale:1.2,duration:.4,stagger:.03,immediateRender:false}},{t + .1:.3f});')


# =================================================================================================
# Раскладка «до/после» (формат «говорю команды - ИИ монтирует») и эффекты окна.
# В этой раскладке #scene (клип 1080×1920) живёт в верхнем окне, координаты «на теле» — как в клипе;
# слой "panel" — координаты самого окна (w×hT, по умолчанию 1000×700).
# =================================================================================================
def ekran_do_posle(r, zagolovok="ИИ-монтаж", podpis="оригинал", x=40, yT=380, hT=700, yB=1110, hB=600, w=1000,
                   y0T=440, y0B=470, fon=("#0B1024", "#1A2A6C")):
    """Раздвоенный экран: сверху смонтированный кадр, снизу исходник с подписью, над всем плашка.
    Вызывать первым. y0T/y0B — с какой высоты клипа начинается окно (по умолчанию от макушки)."""
    k = w / W
    r.split = dict(x=x, yT=yT, hT=hT, yB=yB, hB=hB, w=w, k=k, y0B=y0B)
    r.css.append(f'''#dp-zag{{position:absolute;left:0;right:0;top:286px;text-align:center}}
#dp-zag span{{display:inline-flex;align-items:center;gap:16px;font:60px LatoB;color:#fff;background:{FON};border-radius:20px;padding:6px 30px 8px}}
#dp-zag i{{font-style:normal;color:{AK};font-size:64px}}
#dp-pod{{position:absolute;left:0;right:0;top:{yB + hB + 12}px;text-align:center;font:34px LatoBd;color:rgba(255,255,255,.75);letter-spacing:2px}}''')
    r.add("pod", f'<div class="full" style="background:linear-gradient(180deg,{fon[0]} 0%,{fon[1]} 100%)"></div>'
                 f'<div id="dp-zag"><span><i>✦</i>{zagolovok}</span></div><div id="dp-pod">{podpis}</div>')
    okno_kadr(r, 0, y0T, dur=0)


def okno_kadr(r, t, sy, sx=0, zoom=1.0, sdvig=0, dur=0.45, ease="power3.inOut"):
    """Камера верхнего окна: точка клипа (sx, sy) — в левый верхний угол окна, zoom — крупность,
    sdvig — сдвиг картинки вправо в пикселях окна (освободить место слева)."""
    sc = r.split["k"] * zoom
    v = f'x:{-sx * sc + sdvig:.1f},y:{-sy * sc:.1f},scale:{sc:.5f},transformOrigin:"0px 0px"'
    if dur <= 0:
        r.j(f'tl.set("#scene",{{{v}}},{t:.3f});')
    else:
        r.j(f'tl.to("#scene",{{{v},duration:{dur},ease:"{ease}"}},{t:.3f});')


def komanda(r, t, d, tekst, klyuch=None, y=520, razmer=50, sloy="panel", levo=30, pravo=30, vremena=None):
    """Команда-приказ надписью (как будто сказана ИИ): слова появляются по одному, ключевое — акцентной плашкой.
    Координаты окна; y — верх блока. klyuch — слово (или часть фразы) для акцента."""
    i = r.uid("km")
    slova = tekst.split()
    sp = "".join(f'<span class="w{" k" if klyuch and w.strip(",.:—") in [q.strip(",.:—") for q in klyuch.split()] else ""}">{w}</span> ' for w in slova)
    r.css.append(f'''#{i}{{position:absolute;left:{levo}px;right:{pravo}px;top:{y}px;text-align:center;font:{razmer}px LatoB;line-height:1.28;color:#fff}}
#{i} .w{{background:rgba(13,14,18,.82);border-radius:12px;padding:2px 12px;display:inline-block;margin:3px 0}}
#{i} .k{{background:{AK}}}''' + (f"\n#{i} .w{{opacity:.25}}" if vremena else ""))
    r.add(sloy, f'<div id="{i}" class="fx">{sp}</div>')
    r.okno(f"#{i}", t, d)
    if vremena and len(vremena) == len(slova):  # каждое слово — в момент, когда его говорит голос
        for n, tv in enumerate(vremena):
            r.j(f'tl.fromTo("#{i} .w:nth-of-type({n + 1})",{{opacity:.25}},{{opacity:1,duration:.08,immediateRender:false}},{max(t, tv - .03):.3f});'
                f'tl.fromTo("#{i} .w:nth-of-type({n + 1})",{{scale:1}},{{scale:1.08,duration:.1,yoyo:true,repeat:1,immediateRender:false}},{max(t, tv - .03):.3f});')
    else:
        shag = min(0.12, 0.6 / max(1, len(slova)))
        r.j(f'tl.from("#{i} .w",{{opacity:0,y:18,scale:.8,duration:.16,ease:"back.out(2)",stagger:{shag:.3f},immediateRender:false}},{t:.3f});')


def top_spisok(r, t, d, zagolovok="ТОП-5", punkty=(), sdvig=330, sy=440, shirina=None, cvet=("#101A3C", "#2B4BB8")):
    """Список топ-N на половине окна: кадр уезжает вправо, слева панель, пункты появляются по одному."""
    i = r.uid("ts")
    sp = r.split
    sh = shirina or sdvig + 40
    rows = "".join(f'<div class="{i}p" style="display:flex;gap:14px;align-items:flex-start;margin-bottom:16px"><b style="flex:none;width:44px;height:44px;border-radius:12px;background:{AK};font:28px LatoB;display:flex;align-items:center;justify-content:center">{n + 1}</b>'
                   f'<span style="font:30px LatoBd;line-height:1.15;padding-top:6px">{p}</span></div>' for n, p in enumerate(punkty))
    r.add("panel", f'''<div id="{i}" class="fx" style="left:0;top:0;width:{sh}px;height:{sp["hT"]}px;background:linear-gradient(180deg,{cvet[0]},{cvet[1]});padding:34px 26px;color:#fff;z-index:2;box-shadow:12px 0 30px rgba(0,0,0,.35)">
 <div style="display:inline-block;font:26px LatoB;letter-spacing:2px;border-left:6px solid {AK};padding:2px 12px;margin-bottom:26px">{zagolovok}</div>{rows}</div>''')
    r.okno(f"#{i}", t, d)
    okno_kadr(r, t, sy, sdvig=sdvig - 80); okno_kadr(r, t + d - .3, sy, dur=.3)
    r.j(f'tl.from("#{i}",{{x:-{sh},duration:.45,ease:"power3.out",immediateRender:false}},{t:.3f});')
    n = max(1, len(punkty))
    r.j(f'tl.from("#{i} .{i}p",{{opacity:0,x:-40,duration:.25,ease:"power2.out",stagger:{min(.55, (d - 1.2) / n):.2f},immediateRender:false}},{t + .5:.3f});')


def cvetokorr(r, t, d, polzunki=(("Яркость", 0.15, 0.62), ("Экспозиция", 0.5, 0.78), ("Контраст", 0.5, 0.5), ("Тепло", 0.5, 0.5)),
              filtr_kon="brightness(1.22) contrast(1.12) saturate(1.15)", ev="+0,5 EV"):
    """Цветокоррекция с ползунками: справа панель «Свет», ползунки едут, картинка в окне светлеет.
    polzunki: (имя, начало 0..1, конец 0..1). Фильтр кладётся на #bgv и снимается в конце окна."""
    i = r.uid("cc")
    sp = r.split
    rows = "".join(f'''<div style="margin:12px 0"><div style="display:flex;justify-content:space-between;font:22px LatoBd;color:#C9CCD3"><span>{nm}</span><span id="{i}v{n}">{a * 2 - 1:+.1f}</span></div>
 <div style="position:relative;height:6px;border-radius:3px;background:rgba(255,255,255,.22);margin-top:10px"><i id="{i}h{n}" style="position:absolute;top:-9px;left:0;width:24px;height:24px;margin-left:-12px;border-radius:50%;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.4)"></i></div></div>'''
                   for n, (nm, a, b) in enumerate(polzunki))
    r.add("panel", f'''<div id="{i}" class="fx" style="right:24px;top:{sp["hT"] - 400}px;width:300px;background:rgba(20,22,28,.82);border-radius:20px;padding:18px 22px;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);color:#fff">
 <div style="font:24px LatoB;letter-spacing:2px">СВЕТ</div>{rows}</div>
<div id="{i}e" class="fx" style="left:24px;top:24px;font:24px Mono;font-weight:bold;color:#141413;background:#F2C14E;border-radius:8px;padding:4px 12px">{ev}</div>''')
    r.okno(f"#{i}", t, d); r.okno(f"#{i}e", t + .4, d - .4)
    r.j(f'tl.from("#{i}",{{x:340,duration:.35,ease:"power3.out",immediateRender:false}},{t:.3f});')
    for n, (nm, a, b) in enumerate(polzunki):
        r.j(f'tl.set("#{i}h{n}",{{x:{a * 256:.0f}}},0);')
        if a == b: continue
        tt = t + .35 + n * max(.25, (d - 1.2) / len(polzunki))
        r.j(f'tl.fromTo("#{i}h{n}",{{x:{a * 256:.0f}}},{{x:{b * 256:.0f},duration:.6,ease:"power2.inOut",immediateRender:false}},{tt:.3f});')
        r.j(f'(()=>{{const o={{v:{a * 2 - 1}}},e=document.querySelector("#{i}v{n}");tl.to(o,{{v:{b * 2 - 1},duration:.6,ease:"power2.inOut",onUpdate:()=>{{e.textContent=(o.v>=0?"+":"")+o.v.toFixed(1)}}}},{tt:.3f});}})();')
    r.j(f'tl.set("#bgv",{{filter:"brightness(1) contrast(1) saturate(1)"}},{t:.3f}); tl.to("#bgv",{{filter:"{filtr_kon}",duration:{max(1.0, d - 1.0):.2f},ease:"power1.inOut"}},{t + .35:.3f}); tl.set("#bgv",{{filter:"none"}},{t + d:.3f});')


def karta_na_ladoni(r, t, d, imya="Мой канал", podpis="Telegram-канал", avatar=None, x=330, y=1230,
                    kacha=((0, 0), (12, -10), (-8, 6), (6, -6))):
    """Карточка канала «на ладони»: пульсирует кнопка «+ подписчики» и растёт полоса — без чисел.
    x, y — левый верх карточки в координатах клипа (над областью ладони; точного трекинга нет — покачивание kacha)."""
    i = r.uid("kl")
    av = avatar or r.obl[0]
    r.add("infront", f'''<div id="{i}" class="fx" style="left:{x}px;top:{y}px;width:430px;padding:20px 22px;border-radius:28px;background:rgba(20,22,28,.55);
 backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);border:1.5px solid rgba(255,255,255,.4);box-shadow:0 24px 50px rgba(0,0,0,.45);color:#fff">
 <div style="display:flex;gap:16px;align-items:center"><div style="width:76px;height:76px;border-radius:50%;background:url({r.p(av)}) center 20%/cover;border:3px solid {AK};flex:none"></div>
  <div><div style="font:30px LatoB;line-height:1.1">{imya}</div><div style="font:22px LatoBd;opacity:.75">{podpis}</div></div></div>
 <div style="display:flex;align-items:flex-end;justify-content:space-between;margin-top:16px">
  <div id="{i}k" style="font:28px LatoB;white-space:nowrap;background:{AK};color:#fff;border-radius:30px;padding:10px 22px;box-shadow:0 0 0 0 rgba(217,119,87,.6)">+ подписчики</div>
  <div id="{i}u" style="font:26px LatoB;white-space:nowrap;color:{PLUS}">▲ растёт</div></div>
 <div style="height:8px;border-radius:4px;background:rgba(255,255,255,.2);margin-top:14px;overflow:hidden"><div id="{i}b" style="height:100%;background:{AK};transform-origin:left"></div></div>
</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}",{{scale:.3,y:120,opacity:0,rotationX:50}},{{scale:1,y:0,opacity:1,rotationX:0,duration:.5,ease:"back.out(1.5)",immediateRender:false}},{t:.3f});')
    for n, (dx, dy) in enumerate(kacha[1:]):
        r.j(f'tl.to("#{i}",{{x:{dx},y:{dy},duration:{(d - .6) / (len(kacha) - 1):.2f},ease:"sine.inOut"}},{t + .5 + n * (d - .6) / (len(kacha) - 1):.3f});')
    r.j(f'tl.fromTo("#{i}b",{{scaleX:.05}},{{scaleX:1,duration:{d - .7:.2f},ease:"power1.in",immediateRender:false}},{t + .5:.3f});')
    # без чисел (правило: никаких выдуманных цифр) — пульсирует кнопка «+ подписчики», растёт полоса
    r.j(f'tl.fromTo("#{i}k",{{scale:1,boxShadow:"0 0 0 0px rgba(217,119,87,.6)"}},{{scale:1.08,boxShadow:"0 0 0 18px rgba(217,119,87,0)",duration:.4,repeat:{max(1, int((d - .6) / .4) - 1)},ease:"sine.out",immediateRender:false}},{t + .5:.3f});')
    r.j(f'tl.from("#{i}u",{{scale:0,duration:.25,ease:"back.out(3)",immediateRender:false}},{t + .9:.3f});')


def sfx_dorozhka(r, t, d, zvuki=(("Вжух", "#4C8DF6"), ("Удар", MINUS), ("Щелчок", "#F2C14E"), ("Дзынь", PLUS), ("Свист", "#8B6CEF"), ("Бум", AK)), seed=5):
    """Дорожка звуковых эффектов: внизу окна таймлайн — кадры, волна голоса, плашки SFX встают на дорожку, едет плейхед."""
    i = r.uid("sx")
    sp = r.split
    rnd = random.Random(seed)
    w = sp["w"] - 60
    volna = "".join(f'<i style="position:absolute;left:{x}px;top:{30 - h / 2:.0f}px;width:5px;height:{h:.0f}px;background:{PLUS};border-radius:2px;opacity:.85"></i>'
                    for x, h in ((x, 6 + 46 * abs(math.sin(x * .07)) * rnd.uniform(.4, 1)) for x in range(0, w - 20, 9)))
    kadry = "".join(f'<i style="flex:1;height:64px;background:url({r.p(r.obl[n % len(r.obl)])}) center 30%/cover;border-radius:4px"></i>' for n in range(9))
    chipy = ""
    for n, (nm, c) in enumerate(zvuki):
        x = 20 + n * (w - 160) / max(1, len(zvuki) - 1); row = n % 2
        chipy += f'<div class="{i}c" style="position:absolute;left:{x:.0f}px;top:{176 + row * 46}px;height:38px;padding:0 14px;border-radius:9px;background:{c};font:22px LatoB;color:#141413;display:flex;align-items:center">{nm}</div>'
    r.add("panel", f'''<div id="{i}" class="fx" style="left:30px;top:{sp["hT"] - 300}px;width:{w}px;height:280px;background:rgba(16,17,22,.9);border-radius:18px;padding:12px;overflow:hidden">
 <div style="display:flex;gap:4px">{kadry}</div>
 <div style="position:relative;height:60px;margin-top:10px">{volna}</div>{chipy}
 <i id="{i}p" style="position:absolute;left:30px;top:6px;bottom:6px;width:3px;background:#fff;box-shadow:0 0 8px #fff"></i>
 <div id="{i}m" style="position:absolute;left:0;top:0;font:34px LatoB;color:#fff;text-shadow:0 2px 6px #000">➤</div></div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i}",{{y:320,duration:.4,ease:"power3.out",immediateRender:false}},{t:.3f});')
    r.j(f'tl.from("#{i} .{i}c",{{y:-120,opacity:0,scale:.6,duration:.25,ease:"back.out(2)",stagger:{(d - 1.0) / len(zvuki):.2f},immediateRender:false}},{t + .4:.3f});')
    r.j(f'tl.fromTo("#{i}p",{{x:0}},{{x:{w - 60},duration:{d - .4:.2f},ease:"none",immediateRender:false}},{t + .4:.3f});')
    r.j(f'tl.fromTo("#{i}m",{{x:{w * .7:.0f},y:250}},{{x:{w * .35:.0f},y:190,duration:{d - .5:.2f},ease:"sine.inOut",immediateRender:false}},{t + .4:.3f});')


def veer_titrov(r, t, d, slovo="монтаж", zagolovok="СТИЛИ СУБТИТРОВ"):
    """Веер стилей субтитров: карточки с одним словом в разных стилях раскрываются в перспективе."""
    i = r.uid("vt")
    sp = r.split
    stili = [
        ("01 Плашка", f"background:{AK};color:#fff;font-family:LatoB;padding:0 16px;border-radius:10px"),
        ("02 Контур", "color:transparent;-webkit-text-stroke:2.5px #fff;font-family:LatoB"),
        ("03 Неон", "color:#fff;font-family:LatoB;text-shadow:0 0 8px #FF4FD8,0 0 22px #FF4FD8,0 0 40px #B14BFF"),
        ("04 Жёлтый", "color:#141413;background:#F2C14E;font-family:LatoB;padding:0 14px;transform:skew(-8deg)"),
        ("05 Засечки", "color:#fff;font-family:Serif;font-style:italic"),
        ("06 Градиент", "background:linear-gradient(90deg,#4C8DF6,#FF4FD8);-webkit-background-clip:text;background-clip:text;color:transparent;font-family:LatoB"),
        ("07 Моно", "color:#5EC882;font-family:Mono"),
    ]
    n = len(stili)
    # две дуги: сверху 4 карточки, снизу 3 — каждая читается целиком
    poz = []
    for ryad, kol, y in ((0, 4, sp["hT"] * .2), (1, n - 4, sp["hT"] * .2 + 185)):
        for c in range(kol):
            m = c - (kol - 1) / 2
            poz.append((sp["w"] / 2 + m * 238 - 112, y + abs(m) * 22, m * 7))
    kart = "".join(f'''<div id="{i}k{k}" style="position:absolute;left:{x:.0f}px;top:{y:.0f}px;width:224px;height:160px;border-radius:18px;background:#17181E;border:1.5px solid rgba(255,255,255,.18);
 box-shadow:0 16px 40px rgba(0,0,0,.5)"><div style="position:absolute;left:14px;top:10px;font:17px LatoBd;color:#9A9DA6">{nm}</div>
 <div style="position:absolute;left:0;right:0;top:58px;text-align:center;font-size:44px;line-height:1.1"><span style="display:inline-block;{st}">{slovo}</span></div></div>''' for k, ((nm, st), (x, y, a)) in enumerate(zip(stili, poz)))
    r.add("panel", f'''<div id="{i}" class="fx full" style="background:radial-gradient(ellipse at 50% 50%,rgba(0,0,0,.35),rgba(0,0,0,.8))">
 <div style="position:absolute;left:50%;top:26px;transform:translateX(-50%);font:24px LatoB;letter-spacing:3px;color:#fff;border-left:6px solid {AK};padding:2px 12px;background:rgba(13,14,18,.7)">{zagolovok}</div>{kart}</div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i}",{{opacity:0,duration:.25,immediateRender:false}},{t:.3f});')
    for k, (x, y, a) in enumerate(poz):
        r.j(f'tl.fromTo("#{i}k{k}",{{rotation:{a * 4:.1f},y:260,opacity:0,scale:.6}},{{rotation:{a:.1f},y:0,opacity:1,scale:1,duration:.4,ease:"back.out(1.5)",immediateRender:false}},{t + .15 + .12 * k:.3f});')
    r.j(f'tl.to("#{i}k2",{{scale:1.15,zIndex:20,duration:.25,ease:"back.out(2)"}},{t + d * .65:.3f});')


MIR_JSON = "assets/countries-50m.json"


def planeta(r, t, d, lon=37.6173, lat=55.7558, gorod="Москва", strana="Россия", podpis="мой город", mir=MIR_JSON, t_metka=None):
    """3D-планета: глобус (D3, ортографическая проекция) поворачивается к точке, приближение ×60,
    прицел и метка «Я здесь». Данные стран - world-atlas (ISC, Natural Earth), кладутся в HTML строкой:
    скачать один раз - podgotovka.py mir."""
    i = r.uid("pl")
    sp = r.split
    W2, H2 = (sp["w"], sp["hT"]) if sp else (W, H)
    for u in ("https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js", "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"):
        if u not in r.skripty: r.skripty.append(u)
    if not (r.baza / mir).exists():
        sys.exit(f"нет {mir}: запустите podgotovka.py mir (скачает карту стран world-atlas)")
    data = (r.baza / mir).read_text()
    sloy = "panel" if sp else "overlay"
    # tz — момент прицела и метки; t_metka — когда голос говорит «мой город» (метка-подпись встаёт на t_metka)
    tz = (t_metka - .3) if t_metka else t + .1 + d * .7
    rot = min(d * .4, (tz - t - .1) * .55)
    zum = max(.5, tz - (t + .1 + rot))
    rnd = random.Random(9)
    zvezdy = "".join(f'<i style="position:absolute;left:{rnd.randint(0, W2)}px;top:{rnd.randint(0, H2)}px;width:{rnd.choice([2, 2, 3])}px;height:2px;background:#fff;opacity:{rnd.uniform(.3, .9):.2f}"></i>' for _ in range(90))
    r.add(sloy, f'''<div id="{i}" class="fx full" style="background:radial-gradient(ellipse at 50% 50%,#0E1B3D 0%,#03050C 70%)">{zvezdy}
 <svg id="{i}s" width="{W2}" height="{H2}" style="position:absolute;inset:0"></svg>
 <div id="{i}r" style="position:absolute;left:{W2 / 2 - 70}px;top:{H2 / 2 - 70}px;width:140px;height:140px;border:3px solid #fff;border-radius:50%;opacity:0">
   <i style="position:absolute;left:50%;top:50%;width:22px;height:22px;margin:-11px;border-radius:50%;background:{AK};box-shadow:0 0 0 8px rgba(217,119,87,.35)"></i></div>
 <div id="{i}m" style="position:absolute;left:{W2 / 2 - 20}px;top:{H2 / 2 - 190}px;opacity:0;display:flex;align-items:center;gap:12px;background:rgba(20,22,28,.85);border:1.5px solid rgba(255,255,255,.3);border-radius:16px;padding:10px 18px;color:#fff">
   <div style="width:44px;height:44px;border-radius:50%;background:url({r.p(r.obl[0])}) center 20%/cover;border:2px solid {AK}"></div><div><div style="font:24px LatoB">Я здесь</div><div style="font:20px LatoBd;opacity:.75">{gorod} · {strana}</div></div></div>
 <div id="{i}k" style="position:absolute;left:28px;top:22px;font:20px Mono;color:rgba(255,255,255,.7)">{abs(lat):.2f}°{"S" if lat < 0 else "N"} {abs(lon):.2f}°{"W" if lon < 0 else "E"} · ZOOM ×<span id="{i}z">1</span></div>
 <div id="{i}g" style="position:absolute;left:34px;bottom:30px;opacity:0;color:#fff"><div style="font:40px LatoB">{podpis}</div><div style="font:84px LatoB;color:{AK};line-height:1">{gorod}</div></div>
</div>''')
    r.j(f'''(()=>{{const MIR={data};
const svg=d3.select("#{i}s"), W2={W2}, H2={H2}, R0=Math.min(W2,H2)*0.40;
const pr=d3.geoOrthographic().translate([W2/2,H2/2]).scale(R0).clipAngle(90).precision(.3);
const pg=d3.geoPath(pr), zem=topojson.feature(MIR,MIR.objects.countries);
const okean=svg.append("path").datum({{type:"Sphere"}}).attr("fill","#0B3A75").attr("stroke","#5FA8FF").attr("stroke-width",1.5);
const setka=svg.append("path").datum(d3.geoGraticule10()).attr("fill","none").attr("stroke","rgba(255,255,255,.12)");
const strany=svg.append("path").datum(zem).attr("fill","#3E8E5A").attr("stroke","#9FD6A8").attr("stroke-width",.5);
const tochka=svg.append("circle").attr("r",7).attr("fill","{AK}");
const z=document.querySelector("#{i}z"), o={{a:0,k:0}};
const f=()=>{{const lo=-({lon})+(1-o.a)*120, la=-({lat})*o.a;
pr.rotate([lo,la]).scale(R0*Math.pow(60,o.k));
okean.attr("d",pg); setka.attr("d",pg); strany.attr("d",pg);
const p=pr([{lon},{lat}]); tochka.attr("cx",p?p[0]:-99).attr("cy",p?p[1]:-99);
z.textContent=Math.round(Math.pow(60,o.k)*10)/10;}};
f(); tl.to(o,{{a:1,duration:{rot:.2f},ease:"power2.inOut",onUpdate:f}},{t + .1:.3f});
tl.to(o,{{k:1,duration:{zum:.2f},ease:"power2.in",onUpdate:f}},{t + .1 + rot:.3f});}})();''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i}s",{{scale:.4,opacity:0,transformOrigin:"50% 50%",duration:.5,ease:"power3.out",immediateRender:false}},{t:.3f});')
    r.j(f'tl.fromTo("#{i}r",{{scale:2.4,opacity:0}},{{scale:1,opacity:1,duration:.3,ease:"power3.out",immediateRender:false}},{tz:.3f});')
    r.j(f'tl.fromTo("#{i}m",{{y:30,opacity:0}},{{y:0,opacity:1,duration:.3,ease:"back.out(2)",immediateRender:false}},{tz + .2:.3f});')
    r.j(f'tl.fromTo("#{i}g",{{x:-40,opacity:0}},{{x:0,opacity:1,duration:.3,immediateRender:false}},{tz + .3:.3f});')


def prizyv_kommentariy(r, t, d, slovo="МОНТАЖ", stroki=("Напиши в комментариях", "слово"), podpis="пришлю, как это сделать", nad=(), t_pechat=None, glavnoe=None, pole_tekst=None):
    """Финал-призыв: L3-карточка, ниже поле комментария, в нём печатается слово, кнопка «Отправить» мигает."""
    i = r.uid("pk")
    pole_tekst = pole_tekst or slovo     # что печатается в поле (концовки ВК/ТГ: своё)
    bukvy = "".join(f'<span class="{i}b" style="opacity:0">{c}</span>' for c in pole_tekst)
    glavnoe = glavnoe or f'{stroki[0]}<br>{stroki[1]} <span style="color:{AK}">{slovo}</span>'
    r.add("top", f'''<div id="{i}" class="fx full" style="background:{FON};display:flex;flex-direction:column;justify-content:center;padding:0 80px">
 {"".join(f'<div class="{i}n" style="font:52px LatoB;line-height:1.1;color:{c}">{tx}</div>' for tx, c in nad)}{'<div style="height:44px"></div>' if nad else ''}
 <div style="font:84px LatoB;line-height:1.08;color:#fff">{glavnoe}</div>
 <div style="margin-top:56px;height:110px;border-radius:55px;background:#1E2027;border:2px solid #34363F;display:flex;align-items:center;padding:0 16px 0 30px;gap:18px">
  <div style="width:70px;height:70px;border-radius:50%;background:url({r.p(r.obl[0])}) center 20%/cover;flex:none"></div>
  <div style="flex:1;font:46px LatoB;color:#fff">{bukvy}<i id="{i}c" style="display:inline-block;width:4px;height:48px;background:{AK};vertical-align:middle;margin-left:4px"></i></div>
  <div id="{i}o" style="height:76px;padding:0 28px;border-radius:38px;background:#34363F;font:32px LatoB;color:#fff;display:flex;align-items:center">➤</div></div>
 <div style="font:34px LatoBd;color:{SER};margin-top:28px">{podpis}</div></div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.from("#{i}",{{opacity:0,duration:.25,immediateRender:false}},{t:.3f});')
    if nad:
        r.j(f'tl.from("#{i} .{i}n",{{opacity:0,x:-30,duration:.2,stagger:.12,immediateRender:false}},{t + .05:.3f});')
    tp = t_pechat if t_pechat else t + .5   # слово печатается, когда его говорит голос
    r.j(f'tl.to("#{i} .{i}b",{{opacity:1,duration:.01,stagger:.11}},{tp:.3f});')
    r.j(f'tl.to("#{i}c",{{opacity:0,duration:.01,yoyo:true,repeat:{int(d * 3)},repeatDelay:.15}},{t + .3:.3f});')
    r.j(f'tl.set("#{i}o",{{backgroundColor:"{AK}"}},{tp + .05 + .11 * len(pole_tekst):.3f}); tl.fromTo("#{i}o",{{scale:1}},{{scale:1.15,duration:.15,yoyo:true,repeat:3,immediateRender:false}},{tp + .1 + .11 * len(pole_tekst):.3f});')


def khuk_plashka(r, t, d, chislo=24, stroki=("ЭФФЕКТА", "В ОДНОМ КЛИПЕ"), podpis="сделано с", brend="ИИ", y=285):
    """Хук первых секунд: крупная весёлая плашка над лицом - цифра считается 0→N, плашка выпрыгивает и покачивается,
    справа под ней пилюля «сделано с ИИ» (brend - акцентом, только слово, без логотипов)."""
    i = r.uid("hk")
    r.add("overlay", f'''<div id="{i}" class="fx" style="left:65px;right:65px;top:{y}px">
 <div id="{i}c" style="display:flex;align-items:center;gap:26px;background:#fff;color:#141413;border-radius:34px;padding:14px 34px 18px;
   box-shadow:0 18px 40px rgba(0,0,0,.35);transform-origin:50% 60%">
  <div id="{i}n" style="font:190px LatoB;line-height:.9;color:{AK};min-width:220px;text-align:center;letter-spacing:-4px">{chislo}</div>
  <div style="font:62px LatoB;line-height:1.02;letter-spacing:-.5px">{"<br>".join(stroki)}</div></div>
 <div id="{i}p" style="position:absolute;right:0;top:100%;margin-top:18px;background:{FON};border-radius:40px;padding:10px 26px;font:36px LatoB;color:#fff;white-space:nowrap">
  {podpis} <span style="color:{AK}">{brend}</span></div></div>''')
    r.okno(f"#{i}", t, d)
    r.j(f'tl.fromTo("#{i}c",{{scale:0,rotation:-12}},{{scale:1,rotation:-3,duration:.45,ease:"back.out(2.2)",immediateRender:false}},{t:.3f});')
    r.j(f'(()=>{{const o={{v:0}},e=document.querySelector("#{i}n");tl.fromTo(o,{{v:0}},{{v:{chislo},duration:.7,ease:"power3.out",immediateRender:false,onUpdate:()=>{{e.textContent=Math.round(o.v)}}}},{t + .05:.3f});}})();')
    r.j(f'tl.set("#{i}n",{{textContent:"0"}},0);')
    r.j(f'tl.to("#{i}c",{{rotation:2,duration:.45,ease:"sine.inOut",yoyo:true,repeat:{max(1, int((d - 1.0) / .45))}}},{t + .5:.3f});')
    r.j(f'tl.fromTo("#{i}n",{{scale:1}},{{scale:1.12,duration:.12,yoyo:true,repeat:1,immediateRender:false}},{t + .75:.3f});')
    r.j(f'tl.fromTo("#{i}p",{{scale:0,opacity:0}},{{scale:1,opacity:1,duration:.3,ease:"back.out(2.5)",immediateRender:false}},{t + .55:.3f});')
    r.j(f'tl.to("#{i}",{{scale:1.15,opacity:0,duration:.18,ease:"power2.in"}},{t + d - .18:.3f});')


# Реестр: код → (функция, полное имя, короткое имя — на экране и в озвучке, нужна ли вырезка человека)
EFFEKTY = {
    "steklo": (steklo, "стеклянные виджеты", "стекло", False),
    "vertigo": (vertigo, "вертиго", "вертиго", True),
    "orbita": (orbita, "орбита", "орбита", True),
    "zakhvat": (zakhvat, "захват цели", "прицел", False),
    "vyrezka": (vyrezka, "бумажная вырезка", "вырезка", True),
    "blestki": (blestki, "блёстки и прожектор", "блёстки", False),
    "slovo_za_spinoy": (slovo_za_spinoy, "слово за спиной", "слово сзади", True),
    "cifrovoy_zum": (cifrovoy_zum, "цифровой зум", "зум", False),
    "krolichya_nora": (krolichya_nora, "нора", "нора", False),
    "chat_ui": (chat_ui, "интерфейс ИИ-чата", "чат", False),
    "teatr_teney": (teatr_teney, "театр теней", "тени", True),
    "dozhd_klavish": (dozhd_klavish, "дождь из клавиш", "клавиши", False),
    "chek": (chek, "чек", "чек", False),
    "shtamp": (shtamp, "штамп «отклонено»", "штамп", False),
    "gigantskie_titry": (gigantskie_titry, "гигантские титры", "гигантские титры", True),
    "tochki": (tochki, "точечный портрет", "точки", True),
    "tir_list": (tir_list, "тир-лист", "тир-лист", False),
    "stena_profilya": (stena_profilya, "стена профиля", "профиль", True),
    "krasnyy_kollazh": (krasnyy_kollazh, "красный коллаж", "коллаж", True),
    "veer": (veer, "веер телефонов", "веер", True),
    "karakuli": (karakuli, "каракули", "каракули", False),
    "mrachno": (mrachno, "мрачный свет", "мрак", False),
    "otschet": (otschet, "обратный отсчёт", "отсчёт", True),
    "otezd": (otezd, "отъезд", "отъезд", False),
}

# Эффекты раскладки «до/после» (вызов: (r, t, d, **параметры); раскладку включает ekran_do_posle)
EFFEKTY2 = {
    "ekran_do_posle": (ekran_do_posle, "раздвоенный экран до/после", "до/после"),
    "komanda": (komanda, "команда надписью", "команда"),
    "karta_na_ladoni": (karta_na_ladoni, "карточка на ладони", "ладонь"),
    "top_spisok": (top_spisok, "список топ-N на половине", "топ-N"),
    "cvetokorr": (cvetokorr, "цветокоррекция с ползунками", "свет"),
    "sfx_dorozhka": (sfx_dorozhka, "дорожка звуковых эффектов", "SFX"),
    "veer_titrov": (veer_titrov, "веер стилей субтитров", "субтитры"),
    "planeta": (planeta, "3D-планета с меткой города", "планета"),
    "prizyv_kommentariy": (prizyv_kommentariy, "призыв «напиши в комментариях»", "призыв"),
}
