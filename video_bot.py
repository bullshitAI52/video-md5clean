#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频工具 Bot v2：支持自定义参数（变速/保留原声/静音/掐头）+ 菜单快捷方式
发视频时写参数（如「变速1.2 保留原声 掐头2」）→ 直接处理；不写 → 弹菜单
端口/服务：systemd video-bot · 零 LLM 成本
"""
import json, os, re, subprocess, threading, time, urllib.request, urllib.parse, uuid

TOKEN = open("/root/.hermes/scripts/.video_bot_token").read().strip()
API = f"https://api.telegram.org/bot{TOKEN}"
MD5CLEAN = "http://127.0.0.1:8791/md5clean"
JOBS = {}          # chat -> {tmp, name, params}
PENDING_PARAM = {} # chat -> True  (等用户回复自定义参数)
LOCK = threading.Lock()

def tg(method, **params):
    url = f"{API}/{method}"
    data = {k: v for k, v in params.items() if v is not None}
    try:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        print("tg error:", e)
        return {}

def send_msg(chat, text, kb=None):
    tg("sendMessage", chat_id=chat, text=text,
       reply_markup=json.dumps({"inline_keyboard": kb}) if kb else None)

def send_video(chat, path, caption=None):
    subprocess.run(["curl", "-s", "-F", f"chat_id={chat}", "-F", f"video=@{path}",
                    "-F", f"caption={caption or ''}", f"{API}/sendVideo"],
                   capture_output=True, text=True, timeout=300)

MENU = [[{"text": "🎬 MD5 清洗（默认）", "callback_data": "clean"}],
        [{"text": "🔊 保留原声+变速1.05", "callback_data": "keep105"}],
        [{"text": "🔇 静音", "callback_data": "mute"}],
        [{"text": "⚙️ 自定义参数", "callback_data": "custom"}],
        [{"text": "📝 字幕（未上线）", "callback_data": "subtitle"}]]

HELP = ("🎬 视频工具 Bot\n\n"
        "📤 直接发视频（≤20MB），两种用法：\n\n"
        "1️⃣ 什么都不写 → 弹菜单点按钮\n\n"
        "2️⃣ 视频描述里写参数（自动识别）：\n"
        "   · 变速 1.2 / 1.05（0.5~2 倍）\n"
        "   · 保留原声（音乐原速不变，结尾随视频截断）\n"
        "   · 静音\n"
        "   · 掐头 2（掐头去尾各 2 秒）\n"
        "   · 深度（重编码）\n"
        "   例子：变速1.2 保留原声\n\n"
        "⚠️ 大文件(>20MB)请用网页版：https://www.shuanghai.shop/md5clean/")

def parse_params(caption):
    """从描述文字解析参数，返回 md5clean form 字典"""
    p = {"mode": "fast", "mute": "0", "keepaudio": "0", "trim": "0", "speed": "1"}
    if not caption:
        return p, False
    c = caption.lower()
    found = False
    m = re.search(r"变速\s*([0-9.]+)", caption)
    if m:
        sp = float(m.group(1))
        p["speed"] = str(min(2.0, max(0.5, sp)))
        found = True
    if "保留原声" in c or "原声" in c:
        p["keepaudio"] = "1"; found = True
    if "静音" in c:
        p["mute"] = "1"; found = True
    m = re.search(r"掐头\s*([0-9]+)", caption)
    if m:
        p["trim"] = str(min(60, int(m.group(1))))
        found = True
    if "深度" in c:
        p["mode"] = "deep"; found = True
    return p, found

def params_text(p):
    parts = [p["mode"] == "deep" and "深度清洗" or "快速清洗"]
    if p["speed"] != "1":
        parts.append(f"变速 {p['speed']}x")
    if p["keepaudio"] == "1":
        parts.append("保留原声(音乐随视频截断)")
    if p["mute"] == "1":
        parts.append("静音")
    if p["trim"] != "0":
        parts.append(f"掐头去尾 {p['trim']}s")
    return " + ".join(parts)

def handle_video(chat, file_id, filename, caption=None):
    f = tg("getFile", file_id=file_id)
    if not f.get("ok"):
        send_msg(chat, "❌ 下载失败，请重试")
        return
    tmp = f"/tmp/videobot_{uuid.uuid4().hex}.mp4"
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{TOKEN}/{f['result']['file_path']}", tmp)
    size = os.path.getsize(tmp)
    if size > 20 * 1024 * 1024:
        send_msg(chat, f"⚠️ 视频 {size//1024//1024}MB 超过 20MB 限制\n大文件请用网页版：https://www.shuanghai.shop/md5clean/")
        os.remove(tmp)
        return
    params, found = parse_params(caption)
    with LOCK:
        JOBS[chat] = {"tmp": tmp, "chat": chat, "name": filename or "video.mp4", "params": params}
    if found:
        send_msg(chat, f"📥 收到视频\n⚙️ 参数：{params_text(params)}\n⏳ 处理中…（限速 60% 不卡服务器）")
        process(chat)
    else:
        send_msg(chat, "📥 收到视频！请选择处理方式 👇\n（也可以直接在描述里写参数，如「变速1.2 保留原声」）", MENU)

def process(chat):
    with LOCK:
        job = JOBS.get(chat)
    if not job:
        return
    tmp = job["tmp"]
    form = job["params"]
    # 发送进度消息（后面原地编辑更新）
    sent = tg("sendMessage", chat_id=chat, text="⏳ 提交中…")
    mid = sent.get("result", {}).get("message_id")
    form_args = []
    for k, v in form.items():
        form_args += ["-F", f"{k}={v}"]
    p = subprocess.run(["curl", "-s", "-F", f"file=@{tmp}"] + form_args + [f"{MD5CLEAN}/api/clean"],
                       capture_output=True, text=True, timeout=300)
    try:
        jid = json.loads(p.stdout)["job_id"]
    except Exception:
        if mid:
            tg("editMessageText", chat_id=chat, message_id=mid, text="❌ 提交失败，请重试或改用网页版")
        else:
            send_msg(chat, "❌ 提交失败，请重试或改用网页版")
        return
    last_pct = -1
    for _ in range(120):  # 最多等 6 分钟
        time.sleep(3)
        try:
            st = json.loads(subprocess.run(["curl", "-s", f"{MD5CLEAN}/api/status/{jid}"],
                                           capture_output=True, text=True, timeout=30).stdout)
        except Exception:
            continue
        status, pct = st.get("status"), st.get("progress", 0) or 0
        if status == "queued":
            pos = st.get("pos", 0)
            if mid and pos != last_pct:
                tg("editMessageText", chat_id=chat, message_id=mid,
                   text=f"⏳ 排队中（第 {pos} 位）…")
                last_pct = pos
            continue
        if status == "processing":
            if mid and pct != last_pct:
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                tg("editMessageText", chat_id=chat, message_id=mid,
                   text=f"🔨 处理中 {pct}%\n{bar}")
                last_pct = pct
            continue
        if status == "done":
            od = st.get("orig_dur") or 0
            oad = st.get("orig_audio_dur") or 0
            ad = st.get("audio_dur") or 0
            nd = st.get("duration") or "?"
            md5b = st.get("md5_before") or "-"
            md5a = st.get("md5_after") or "-"
            # 音乐对比说明
            if oad == 0:
                music_line = "🎵 音乐: 无音频"
            elif ad == 0:
                music_line = "🎵 音乐: 已去除"
            else:
                music_line = f"🎵 音乐: {oad}s → {ad}s" + ("（原速保留，随视频截断）" if oad > ad else "")
            diff = f"（缩短 {round((1 - float(str(nd).replace('s','')) / od) * 100)}%）" if od and "s" in str(nd) and float(str(nd).replace("s", "")) < od else ""
            summary = (f"✅ 完成！\n"
                       f"⏱ 视频: {od}s → {nd} {diff}\n"
                       f"{music_line}\n"
                       f"🧬 MD5: {md5b[:16]}… → {md5a[:16]}…\n"
                       f"💾 {st.get('size')}")
            if mid:
                tg("editMessageText", chat_id=chat, message_id=mid, text=summary)
            out = f"/tmp/videobot_out_{uuid.uuid4().hex}.mp4"
            subprocess.run(["curl", "-s", "-o", out, f"http://127.0.0.1:8791{st['url']}"], timeout=300)
            send_video(chat, out, summary)
            os.remove(out); os.remove(tmp)
            with LOCK:
                JOBS.pop(chat, None)
            return
        if status == "error":
            if mid:
                tg("editMessageText", chat_id=chat, message_id=mid, text=f"❌ 处理失败: {st.get('error','')}")
            else:
                send_msg(chat, f"❌ 处理失败: {st.get('error','')}")
            return
    send_msg(chat, "⏰ 处理超时，请改用网页版")

def handle_callback(chat, data):
    with LOCK:
        job = JOBS.get(chat)
    if data == "subtitle":
        send_msg(chat, "📝 字幕功能开发中，敬请期待（需要 Whisper 模型）")
        return
    if data == "custom":
        PENDING_PARAM[chat] = True
        send_msg(chat, "⚙️ 请回复参数，格式如：\n变速 1.2 保留原声 掐头 2\n（支持：变速/保留原声/静音/掐头/深度）")
        return
    if not job:
        send_msg(chat, "没有待处理的视频，请先发送一个视频")
        return
    if data == "clean":
        job["params"] = {"mode": "fast", "mute": "0", "keepaudio": "0", "trim": "0", "speed": "1"}
    elif data == "keep105":
        job["params"] = {"mode": "fast", "mute": "0", "keepaudio": "1", "trim": "0", "speed": "1.05"}
    elif data == "mute":
        job["params"] = {"mode": "fast", "mute": "1", "keepaudio": "0", "trim": "0", "speed": "1"}
    send_msg(chat, f"⏳ 处理中…\n⚙️ {params_text(job['params'])}")
    process(chat)

def get_updates(offset):
    r = tg("getUpdates", offset=offset, timeout=30)
    return r.get("result", []) if r.get("ok") else []

def main():
    offset = 0
    while True:
        try:
            for u in get_updates(offset):
                offset = u["update_id"] + 1
                try:
                    msg = u.get("message") or u.get("edited_message") or {}
                    cb = u.get("callback_query")
                    if cb:
                        handle_callback(cb["message"]["chat"]["id"], cb["data"])
                        continue
                    chat = msg.get("chat", {}).get("id")
                    if not chat:
                        continue
                    text = msg.get("text", "")
                    # 自定义参数输入（等待状态）
                    if PENDING_PARAM.get(chat):
                        PENDING_PARAM.pop(chat, None)
                        with LOCK:
                            job = JOBS.get(chat)
                        if not job:
                            send_msg(chat, "没有待处理的视频，请先发送一个视频")
                            continue
                        params, found = parse_params(text)
                        if not found:
                            send_msg(chat, "❌ 没识别到参数，格式如：变速 1.2 保留原声")
                            continue
                        job["params"] = params
                        send_msg(chat, f"⚙️ 参数：{params_text(params)}\n⏳ 处理中…")
                        process(chat)
                        continue
                    video = msg.get("video") or msg.get("video_note") or \
                            (msg.get("document") if msg.get("document", {}).get("mime_type", "").startswith("video") else None)
                    if video:
                        fname = msg.get("video", {}).get("file_name") or msg.get("document", {}).get("file_name") or "video.mp4"
                        handle_video(chat, video["file_id"], fname, text)
                    elif text == "/start" or text == "/help":
                        send_msg(chat, HELP)
                except Exception as e:
                    print("handler error:", e)
                    try:
                        send_msg(u.get("message", {}).get("chat", {}).get("id")
                                 or (u.get("callback_query", {}).get("message", {}).get("chat", {}).get("id")),
                                 f"⚠️ 处理出错，请重试（{type(e).__name__}）")
                    except Exception:
                        pass
        except Exception as e:
            print("main loop error:", e)
        time.sleep(1)

if __name__ == "__main__":
    main()
