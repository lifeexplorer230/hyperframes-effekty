#!/usr/bin/env bash
# Новый проект ролика: папка с шаблоном HyperFrames, шрифтами и вашим клипом.
#   bash novyj_proekt.sh папка-ролика путь/к/клипу.mp4
set -euo pipefail
P=${1:?укажите папку проекта}; K=${2:?укажите клип .mp4}
DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$P/assets"
cp -R "$DIR/../shablon/." "$P/"
# клип → 1080×1920, 25 к/с (эффекты рассчитаны на эту сетку), голос отдельно
ffmpeg -loglevel error -y -i "$K" -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=25" \
  -c:v libx264 -crf 18 -g 25 -pix_fmt yuv420p -c:a aac -b:a 192k "$P/assets/klip.mp4"
ffmpeg -loglevel error -y -i "$P/assets/klip.mp4" -vn -ac 1 -ar 48000 "$P/assets/golos.wav" || echo "в клипе нет звука - ролик будет без голоса"
echo "готово: $P (assets/klip.mp4, assets/golos.wav, шрифты, hyperframes.json)"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$P/assets/klip.mp4" | awk '{printf "длина клипа: %.2f с\n", $1}'
