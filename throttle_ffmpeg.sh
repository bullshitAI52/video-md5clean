#!/usr/bin/env bash
# 限速视频处理：ffmpeg + cpulimit（按 PID 限速，防止 1 核服务器被占满）
# 用法: throttle_ffmpeg.sh <输入> <输出> [CPU上限%] [额外ffmpeg参数...]
set -u
IN="$1"; OUT="$2"; LIMIT="${3:-60}"; shift 3
[ -f "$IN" ] || { echo "输入文件不存在"; exit 1; }
/usr/bin/ffmpeg -y -i "$IN" "$@" "$OUT" > /tmp/ffmpeg_throttled.log 2>&1 &
FPID=$!
nice -n 19 cpulimit -l "$LIMIT" -p "$FPID" > /dev/null 2>&1 &
CPID=$!
wait "$FPID"
RC=$?
kill "$CPID" 2>/dev/null
if [ $RC -eq 0 ] && [ -f "$OUT" ]; then
  echo "OK: $OUT"
else
  echo "FAIL: $(tail -3 /tmp/ffmpeg_throttled.log)"
  exit 1
fi
