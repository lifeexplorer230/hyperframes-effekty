#!/usr/bin/env bash
# Лист кадров с временем на каждом - быстро проверить ролик глазами (или показать ИИ-агенту картинкой).
#   bash list.sh render.mp4 [шаг_с=0.5] [ширина_кадра=216] [выход=list.jpg] [колонок=10]
set -euo pipefail
V=$1; S=${2:-0.5}; WD=${3:-216}; O=${4:-list.jpg}; C=${5:-10}
DIR=$(cd "$(dirname "$0")" && pwd)
FONT="$DIR/../shablon/assets/fonts/DejaVuSansMono.ttf"
[ -f "$FONT" ] || FONT="assets/fonts/DejaVuSansMono.ttf"
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
N=$(awk -v d="$D" -v s="$S" 'BEGIN{n=d/s; print (n==int(n))?n:int(n)+1}')
R=$(( (N + C - 1) / C ))
ffmpeg -loglevel error -y -i "$V" -vf "fps=1/$S,scale=$WD:-1,drawtext=fontfile='$FONT':text='%{pts\:flt}':x=4:y=h-26:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7,tile=${C}x${R}" -frames:v 1 -q:v 3 "$O"
echo "лист: $O ($N кадров, шаг $S с)"
