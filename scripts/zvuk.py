#!/usr/bin/env python3
"""Звук ролика (необязательный шаг): звуки-акценты на моменты эффектов + фоновая музыка с проседанием под речь +
мастер −14 LUFS / пик ≤ −1,5 dBTP (двухпроходный loudnorm). Видео не перекодируется (-c:v copy). Только ffmpeg.

  python3 zvuk.py render.mp4 gotovo.mp4 [--zvuki zvuki.json] [--muzyka fon.mp3] [--muzyka-lufs -30] [--bez-muzyki-v-konce 3]

zvuki.json - список: [{"t": 3.2, "fayl": "sfx/whoosh.wav", "db": -3}, ...] (пути от папки проекта; db - усиление файла).
Звуки и музыку берите свои или с лицензией, разрешающей использование без указания автора (CC0 и т. п.).
Без --zvuki и --muzyka скрипт просто выравнивает громкость голоса.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path


def dlina(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                                capture_output=True, text=True, check=True).stdout)


def izmerit(f, flt):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", flt + ":print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return json.loads(re.findall(r"\{[^{}]+\}", err)[-1])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("vhod"); ap.add_argument("vyhod")
    ap.add_argument("--zvuki"); ap.add_argument("--muzyka")
    ap.add_argument("--muzyka-lufs", type=float, default=-30); ap.add_argument("--bez-muzyki-v-konce", type=float, default=3)
    a = ap.parse_args()
    L = dlina(a.vhod)
    vhody = ["-i", a.vhod]; f = ["[0:a]aformat=channel_layouts=mono,aresample=48000[vox0]"]; miks = ["[vox0]"]
    if a.zvuki:
        for n, z in enumerate(json.loads(Path(a.zvuki).read_text(encoding="utf-8"))):
            if not Path(z["fayl"]).exists():
                sys.exit(f"нет файла звука {z['fayl']}")
            vhody += ["-i", z["fayl"]]; k = len(vhody) // 2 - 1; ms = int(z["t"] * 1000)
            f.append(f"[{k}:a]aformat=channel_layouts=mono,aresample=48000,volume={z.get('db', 0)}dB,adelay={ms}:all=1[z{n}]")
            miks.append(f"[z{n}]")
    golos = "[vox]"
    f.append(f"{''.join(miks)}amix=inputs={len(miks)}:duration=first:normalize=0,asplit=2[vox][sc]" if len(miks) > 1
             else "[vox0]asplit=2[vox][sc]")
    if a.muzyka:
        vhody += ["-stream_loop", "-1", "-i", a.muzyka]; k = len([x for x in vhody if x == "-i"]) - 1
        konec = max(1.0, L - a.bez_muzyki_v_konce)
        f.append(f"[{k}:a]atrim=0:{L:.2f},asetpts=PTS-STARTPTS,aformat=channel_layouts=mono,aresample=48000,"
                 f"loudnorm=I={a.muzyka_lufs}:TP=-9:LRA=11,afade=t=out:st={max(0.0, konec - 1.2):.2f}:d=1.2[mus]")
        f.append("[mus][sc]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=350[musd]")
        f.append(f"{golos}[musd]amix=inputs=2:duration=first:normalize=0[a]")
    else:
        f.append(f"{golos}anull[a]"); f.append("[sc]anullsink")
    smes = Path(a.vyhod).with_suffix(".smes.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *vhody, "-filter_complex", ";".join(f), "-map", "[a]", "-ar", "48000", str(smes)], check=True)
    m = izmerit(smes, "loudnorm=I=-14:TP=-1.5:LRA=11")
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    gain = 0.0
    for _ in range(4):  # после AAC и на коротких клипах громкость сдвигается - подгоняем усилением, лимитер держит пик
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.vhod, "-i", str(smes), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-af", ln + f",volume={gain:.2f}dB,alimiter=limit=0.8:level=false:attack=2:release=40",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", a.vyhod], check=True)
        itog = izmerit(a.vyhod, "loudnorm=I=-14:TP=-1.5:LRA=11")
        i, pk = float(itog["input_i"]), float(itog["input_tp"])
        if abs(i + 14) <= 0.3 and pk <= -1.0:
            break
        gain += (-14 - i) if pk <= -1.0 else min(-14 - i, -0.3)
    smes.unlink()
    print(f"готово: {a.vyhod} | {i} LUFS | пик {pk} dBTP")


if __name__ == "__main__":
    main()
