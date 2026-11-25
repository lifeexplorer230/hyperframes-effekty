#!/usr/bin/env python3
"""Распознавание речи клипа со временем каждого слова → assets/slova.json. Запускать из папки проекта.

  python3 rech.py raspoznat [assets/golos.wav] [--model small] [--yazyk ru]   → assets/slova.json
  python3 rech.py pokazat                       → слова с временем (по строке на фразу) - чтобы расставить эффекты
  python3 rech.py najti вертиго [--posle 3.0]  → время первого слова, похожего на «вертиго», после 3,0 с

Движок: faster-whisper (pip install faster-whisper) → если нет, openai-whisper (pip install openai-whisper).
Готовый транскрипт тоже подходит: `npx hyperframes transcribe` пишет JSON со словами - укажите его как вход
(любой JSON со списком {"text"|"word"|"w", "start"|"s", "end"|"e"}).
Формат slova.json: {"raspoznano": [{"w": "слово", "s": 1.23, "e": 1.56}, ...]}
"""
import argparse, json, re, sys
from pathlib import Path

SLOVA = Path("assets/slova.json")


def norm(w):
    return re.sub(r"[^\wё-]", "", w.lower()).replace("ё", "е")


def iz_json(f):
    """Импорт стороннего транскрипта: ищем в JSON все объекты со словом и временем."""
    out = []
    def obhod(x):
        if isinstance(x, dict):
            w = x.get("w", x.get("word", x.get("text")))
            s = x.get("s", x.get("start")); e = x.get("e", x.get("end"))
            if isinstance(w, str) and isinstance(s, (int, float)) and " " not in w.strip():
                out.append({"w": w.strip(), "s": round(float(s), 3), "e": round(float(e if e is not None else s), 3)})
                return
            for v in x.values(): obhod(v)
        elif isinstance(x, list):
            for v in x: obhod(v)
    obhod(json.loads(Path(f).read_text(encoding="utf-8")))
    return sorted(out, key=lambda o: o["s"])


def raspoznat(f, model, yazyk):
    if f.suffix.lower() == ".json":
        return iz_json(f)
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(model, device="auto", compute_type="int8")
        segs, _ = m.transcribe(str(f), language=yazyk, word_timestamps=True, vad_filter=True)
        return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for sg in segs for w in sg.words]
    except ImportError:
        pass
    try:
        import whisper
        res = whisper.load_model(model).transcribe(str(f), language=yazyk, word_timestamps=True)
        return [{"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3)}
                for sg in res["segments"] for w in sg.get("words", [])]
    except ImportError:
        sys.exit("нет движка распознавания: python3 -m pip install faster-whisper  (или openai-whisper)")


def zagruzit(f=SLOVA):
    if not Path(f).exists():
        sys.exit(f"нет {f}: сначала python3 rech.py raspoznat")
    return json.loads(Path(f).read_text(encoding="utf-8"))["raspoznano"]


def najti(slova, iskomoe, posle=0.0):
    """Время начала первого слова после `posle`, похожего на `iskomoe` (совпадают первые 4 буквы основы).
    Для фразы из нескольких слов ищется её первое слово. None - не нашлось."""
    q = norm(iskomoe.split()[0])[:4]
    for w in slova:
        if w["s"] >= posle - 0.05 and norm(w["w"]).startswith(q):
            return w["s"]
    return None


def vremena(slova, t, n):
    """Времена n слов подряд, начиная с первого слова не раньше t; None, если слов не хватает."""
    k = next((j for j, w in enumerate(slova) if w["s"] >= t - 0.05), None)
    if k is None or k + n > len(slova):
        return None
    return [w["s"] for w in slova[k:k + n]]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("chto", choices=["raspoznat", "pokazat", "najti"])
    ap.add_argument("arg", nargs="?", default=None)
    ap.add_argument("--model", default="small"); ap.add_argument("--yazyk", default="ru")
    ap.add_argument("--posle", type=float, default=0.0)
    a = ap.parse_args()
    if a.chto == "raspoznat":
        f = Path(a.arg or "assets/golos.wav")
        sl = raspoznat(f, a.model, a.yazyk)
        SLOVA.parent.mkdir(parents=True, exist_ok=True)
        SLOVA.write_text(json.dumps({"raspoznano": sl}, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"{SLOVA}: {len(sl)} слов, {sl[0]['s'] if sl else 0:.2f}–{sl[-1]['e'] if sl else 0:.2f} с")
    elif a.chto == "pokazat":
        sl = zagruzit(); stroka = []
        for n, w in enumerate(sl):
            stroka.append(f"{w['s']:.2f} {w['w']}")
            if n + 1 == len(sl) or sl[n + 1]["s"] - w["e"] > 0.35 or len(stroka) >= 8:
                print(" | ".join(stroka)); stroka = []
    else:
        t = najti(zagruzit(), a.arg or "", a.posle)
        print("не нашлось" if t is None else f"{t:.2f}")
