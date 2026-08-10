#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频 MD5 清洗工具 v3：多文件排队 + CPU限速 + 保留原声 + 历史保存
- 快速清洗: 无损重封装 | 深度清洗: 重编码 H.264
- 可选: 静音 / 保留原声 / 掐头去尾 / 变速
- 处理后文件保留 24h 供下载（可重复下载、可删除）
端口 8791; nginx: /md5clean/ -> 127.0.0.1:8791/
"""
import hashlib, os, shutil, subprocess, threading, time, uuid, json
from flask import Flask, request, render_template_string, send_file, jsonify

app = Flask(__name__)
BASE = "/tmp/md5clean"
MAX_SIZE = 1024 * 1024 * 1024  # 1GB
CPU_LIMIT = 60
KEEP_HOURS = 24
os.makedirs(BASE, exist_ok=True)

QUEUE = []
JOBS = {}
LOCK = threading.Lock()

PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>视频 MD5 清洗工具</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:linear-gradient(160deg,#0f172a 0%,#1e293b 40%,#0f172a 100%);min-height:100vh;color:#e2e8f0;padding:16px}
.wrap{max-width:640px;margin:0 auto}
.header{text-align:center;padding:24px 0 16px}
.header h1{font-size:26px;background:linear-gradient(90deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{font-size:13px;color:#94a3b8;margin-top:6px}
.card{background:rgba(30,41,59,.75);border:1px solid rgba(148,163,184,.15);border-radius:16px;padding:20px;margin:14px 0;backdrop-filter:blur(8px)}
.card h2{font-size:15px;color:#cbd5e1;margin-bottom:12px}
.drop{border:2px dashed rgba(96,165,250,.4);border-radius:12px;padding:28px 16px;text-align:center;cursor:pointer;transition:.2s;background:rgba(15,23,42,.4)}
.drop:hover,.drop.over{border-color:#60a5fa;background:rgba(96,165,250,.08)}
.drop .big{font-size:40px}
.drop .t{font-size:14px;color:#e2e8f0;margin-top:8px}
.drop .s{font-size:12px;color:#64748b;margin-top:4px}
.opts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}
.opt{background:rgba(15,23,42,.5);border:1px solid rgba(148,163,184,.2);border-radius:10px;padding:10px 12px;font-size:13px;cursor:pointer;transition:.15s;display:flex;align-items:center;gap:8px;user-select:none}
.opt:hover{border-color:#60a5fa}
.opt.on{border-color:#60a5fa;background:rgba(96,165,250,.15)}
.opt input[type=number]{width:56px;background:#0f172a;border:1px solid #475569;border-radius:6px;color:#e2e8f0;padding:3px 6px;font-size:13px;text-align:center}
.opt input[type=checkbox]{display:none}
.mode{display:flex;gap:8px;margin-top:12px}
.mbtn{flex:1;padding:10px;border-radius:10px;border:1px solid rgba(148,163,184,.2);background:rgba(15,23,42,.5);color:#cbd5e1;font-size:13px;cursor:pointer;text-align:center;transition:.15s}
.mbtn.on{background:linear-gradient(90deg,#2563eb,#7c3aed);border-color:transparent;color:#fff;font-weight:600}
.btn{width:100%;margin-top:14px;padding:14px;border:none;border-radius:12px;background:linear-gradient(90deg,#2563eb,#7c3aed);color:#fff;font-size:16px;font-weight:700;cursor:pointer;transition:.2s}
.btn:hover{filter:brightness(1.15)}
.btn:disabled{opacity:.5;cursor:not-allowed}
.job{background:rgba(15,23,42,.55);border:1px solid rgba(148,163,184,.15);border-radius:12px;padding:12px 14px;margin:10px 0}
.job .row1{display:flex;justify-content:space-between;align-items:center;gap:8px}
.job .name{font-size:14px;font-weight:600;color:#e2e8f0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.job .st{font-size:12px;white-space:nowrap}
.job .meta{font-size:12px;color:#64748b;margin-top:6px;word-break:break-all;line-height:1.6}
.job .meta code{color:#93c5fd;background:rgba(59,130,246,.12);padding:1px 5px;border-radius:4px;font-size:11px}
.bar{height:5px;background:#1e293b;border-radius:3px;margin-top:8px;overflow:hidden}
.bar i{display:block;height:100%;width:0%;background:linear-gradient(90deg,#60a5fa,#a78bfa);transition:width .4s}
.st.q{color:#94a3b8}.st.p{color:#60a5fa}.st.ok{color:#4ade80}.st.err{color:#f87171}
.dl{display:inline-block;margin-top:8px;padding:7px 16px;border-radius:8px;background:linear-gradient(90deg,#059669,#10b981);color:#fff;font-size:13px;font-weight:600;text-decoration:none}
.del{display:inline-block;margin-top:8px;margin-left:8px;padding:7px 12px;border-radius:8px;background:rgba(248,113,113,.15);color:#f87171;font-size:12px;cursor:pointer;border:1px solid rgba(248,113,113,.3)}
.empty{text-align:center;color:#64748b;font-size:13px;padding:20px 0}
.foot{text-align:center;font-size:11px;color:#475569;padding:14px 0 6px}
.toast{position:fixed;left:50%;bottom:80px;transform:translateX(-50%);background:rgba(15,23,42,.95);border:1px solid rgba(74,222,128,.4);color:#4ade80;padding:10px 18px;border-radius:10px;font-size:14px;z-index:99;display:none;max-width:85%;text-align:center;box-shadow:0 4px 16px rgba(0,0,0,.4)}
.toast.err{border-color:rgba(248,113,113,.4);color:#f87171}
.spin{display:inline-block;width:12px;height:12px;border:2px solid #60a5fa;border-top-color:transparent;border-radius:50%;animation:sp .8s linear infinite;vertical-align:-1px;margin-right:4px}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<div class="wrap">
<div class="header">
<h1>🎬 视频 MD5 清洗 <span style="font-size:12px;background:rgba(96,165,250,.2);color:#60a5fa;padding:2px 8px;border-radius:6px;vertical-align:middle">v3.3</span></h1>
<p>上传 → 排队处理 → 下载清洗后的视频 · 文件保留 24 小时</p>
</div>

<div class="card">
<h2>📤 上传视频（可多选，每个最大 1GB）</h2>
<label class="drop" id="drop" for="f">
<div class="big">📁</div>
<div class="t">点击选择 或 拖拽视频到这里</div>
<div class="s" id="fileinfo">支持 mp4 / mkv / avi / mov / flv 等</div>
<div class="s" style="margin-top:6px"><span id="folderlink" style="color:#60a5fa;text-decoration:underline;cursor:pointer">📂 或选择整个文件夹批量上传</span></div>
</label>
<input type="file" id="f" accept="video/*,.mp4,.mkv,.avi,.mov,.flv,.ts,.wmv,.rmvb,.webm" multiple hidden>
<input type="file" id="fold" webkitdirectory multiple hidden>
<div id="upwrap" style="display:none;margin-top:12px">
<div class="upinfo" id="upinfo" style="font-size:12px;color:#94a3b8;margin-bottom:6px"></div>
<div class="bar"><i id="upfill" style="width:0%"></i></div>
</div>

<div class="opts">
<label class="opt"><input type="checkbox" id="keepaudio"><span>🔊</span> 保留原声</label>
<label class="opt"><input type="checkbox" id="mute"><span>🔇</span> 静音</label>
<label class="opt"><input type="checkbox" id="trimchk"><span>✂️</span> 掐头去尾 <input type="number" id="trim" value="1" min="0" max="60" inputmode="decimal"> 秒</label>
<label class="opt"><input type="checkbox" id="speedchk"><span>⚡</span> 变速 <input type="number" id="speed" value="1.05" step="0.05" min="0.5" max="2" inputmode="decimal"> 倍</label>
</div>

<div class="mode">
<div class="mbtn on" id="mfast">⚡ 快速清洗（无损）</div>
<div class="mbtn" id="mdeep">🔨 深度清洗（重编码）</div>
</div>

<button class="btn" id="btn">开始处理</button>
</div>

<div class="card">
<h2>📋 处理队列 <span style="color:#64748b;font-size:12px" id="qcount"></span></h2>
<div id="jobs"><div class="empty">暂无任务</div></div>
</div>

<div class="foot">文件处理完成后保留 24 小时 · CPU 限速 60% 不卡机 · 隐私自动清除</div>
</div>
<div class="toast" id="toast"></div>

<script>
const jobs={},el={};
el.drop=document.getElementById('drop');el.f=document.getElementById('f');
el.btn=document.getElementById('btn');el.jobs=document.getElementById('jobs');
el.qcount=document.getElementById('qcount');
let mode='fast';
document.getElementById('mfast').onclick=()=>{mode='fast';document.getElementById('mfast').classList.add('on');document.getElementById('mdeep').classList.remove('on')};
document.getElementById('mdeep').onclick=()=>{mode='deep';document.getElementById('mdeep').classList.add('on');document.getElementById('mfast').classList.remove('on')};
document.getElementById('trimchk').onchange=e=>document.getElementById('trim').style.opacity=e.target.checked?'1':'.4';
document.getElementById('speedchk').onchange=e=>document.getElementById('speed').style.opacity=e.target.checked?'1':'.4';
// 数字框点击/触摸时不要触发复选框切换
['trim','speed'].forEach(id=>{
  const el=document.getElementById(id);
  el.onclick=e=>{e.stopPropagation();};
  el.onpointerdown=e=>{e.stopPropagation();};
});
el.drop.onclick=()=>{};  // label for="f" 原生触发文件选择（移动端可靠）
document.getElementById('folderlink').onclick=e=>{e.preventDefault();e.stopPropagation();el.fold.click()};
el.fold=document.getElementById('fold');
el.fold.onchange=()=>{
  const vids=['mp4','mkv','avi','mov','flv','ts','wmv','rmvb','webm','m4v','mpg','mpeg','3gp'];
  const files=Array.from(el.fold.files).filter(f=>{
    const ext=(f.name.split('.').pop()||'').toLowerCase();
    return vids.includes(ext);
  });
  if(!files.length){alert('文件夹里没有视频文件');return}
  upload(files);
  el.fold.value='';
};
el.drop.ondragover=e=>{e.preventDefault();el.drop.classList.add('over')};
el.drop.ondragleave=()=>el.drop.classList.remove('over');
el.drop.ondrop=e=>{e.preventDefault();el.drop.classList.remove('over');if(e.dataTransfer.files.length)upload(e.dataTransfer.files)};
el.f.onchange=()=>{if(el.f.files.length)upload(el.f.files)};
function upload(files){
  const st=document.getElementById('fileinfo');
  const upwrap=document.getElementById('upwrap'),upinfo=document.getElementById('upinfo'),upfill=document.getElementById('upfill');
  st.textContent='已选 '+files.length+' 个文件';
  upwrap.style.display='block';
  const opt={mode:mode,
    mute:document.getElementById('mute').checked?'1':'0',
    keepaudio:document.getElementById('keepaudio').checked?'1':'0',
    trim:document.getElementById('trimchk').checked?document.getElementById('trim').value:'0',
    speed:document.getElementById('speedchk').checked?document.getElementById('speed').value:'1'};
  let i=0;
  (async()=>{
    for(const f of files){
      i++;
      upfill.style.width='0%';
      upinfo.textContent='📤 上传中 ('+i+'/'+files.length+'): '+f.name;
      try{
        const j=await xhrUpload(f,opt,(pct)=>upfill.style.width=pct+'%');
        if(j.ok){
          addJob(j.job_id,f.name);
          showToast('✅ '+f.name+' 上传成功，已加入队列');
        }else{showToast('❌ '+f.name+' 上传失败: '+j.error,true)}
      }catch(e){showToast('❌ '+f.name+' 网络错误',true)}
    }
    upwrap.style.display='none';
    st.textContent='全部提交完成，排队处理中…';
    el.f.value='';
    showToast('🎉 全部 '+files.length+' 个文件已提交，开始排队处理');
    setTimeout(()=>{const q=document.getElementById('jobs');if(q)q.scrollIntoView({behavior:'smooth'})},400);
  })();
}
function xhrUpload(f,opt,onprogress){
  return new Promise((resolve,reject)=>{
    const xhr=new XMLHttpRequest();
    xhr.open('POST','/md5clean/api/clean');
    xhr.upload.onprogress=e=>{if(e.lengthComputable)onprogress(Math.round(e.loaded/e.total*100))};
    xhr.onload=()=>{try{resolve(JSON.parse(xhr.responseText))}catch(e){reject(e)}};
    xhr.onerror=()=>reject(new Error('network'));
    const fd=new FormData();
    fd.append('file',f);
    for(const k in opt)fd.append(k,opt[k]);
    xhr.send(fd);
  });
}
function addJob(id,name){jobs[id]={name:name,status:'上传中'};render();poll(id)}
async function poll(id){
  while(jobs[id]){
    await new Promise(r=>setTimeout(r,2000));
    try{
      const r=await fetch('/md5clean/api/status/'+id);
      const j=await r.json();
      if(!jobs[id])return;
      if(j.status==='queued'){jobs[id].status='q';jobs[id].pos=j.pos}
      else if(j.status==='processing')jobs[id].status='p';
      else if(j.status==='done'){jobs[id].status='ok';jobs[id].md5b=j.md5_before;jobs[id].md5a=j.md5_after;jobs[id].url=j.url;jobs[id].size=j.size;jobs[id].dur=j.duration}
      else if(j.status==='error'){jobs[id].status='err';jobs[id].err=j.error}
      render();
      if(j.status==='done'||j.status==='error')return;
    }catch(e){}
  }
}
function del(id){
  if(!confirm('删除这个任务的文件？'))return;
  fetch('/md5clean/api/delete/'+id).then(()=>{delete jobs[id];render()});
}
function render(){
  const ids=Object.keys(jobs);
  el.qcount.textContent=ids.length?'（共 '+ids.length+' 个）':'';
  if(!ids.length){el.jobs.innerHTML='<div class="empty">暂无任务</div>';return}
  el.jobs.innerHTML=ids.map(id=>{
    const j=jobs[id];
    let st='',bar='';
    if(j.status==='q'){st='<span class="st q">⏳ 排队中</span>'}
    else if(j.status==='p'){st='<span class="st p"><span class="spin"></span>处理中…</span>';bar='<div class="bar"><i style="width:60%"></i></div>'}
    else if(j.status==='ok'){st='<span class="st ok">✅ 完成</span>';bar='<div class="bar"><i style="width:100%;background:linear-gradient(90deg,#059669,#10b981)"></i></div>'}
    else if(j.status==='err'){st='<span class="st err">❌ 失败</span>'}
    else if(j.status==='上传中'){st='<span class="st q">📤 上传中</span>'}
    let meta='';
    if(j.md5a)meta='<div class="meta">MD5: <code>'+j.md5b+'</code> → <code>'+j.md5a+'</code><br>时长 '+j.dur+' · 大小 '+j.size+'</div>';
    if(j.err)meta='<div class="meta" style="color:#f87171">'+esc(j.err)+'</div>';
    const dl=(j.url)?'<a class="dl" href="'+j.url+'">⬇️ 下载</a>':'';
    const delb='<span class="del" onclick="del(\''+id+'\')">🗑 删除</span>';
    return '<div class="job"><div class="row1"><span class="name">'+esc(j.name)+'</span>'+st+'</div>'+bar+meta+dl+delb+'</div>';
  }).join('');
}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function showToast(msg,isErr){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast'+(isErr?' err':'');
  t.style.display='block';
  clearTimeout(t._timer);
  t._timer=setTimeout(()=>t.style.display='none',3000);
}
loadHistory();
function loadHistory(){
  fetch('/md5clean/api/list').then(r=>r.json()).then(d=>{
    (d.jobs||[]).forEach(j=>{
      if(jobs[j.id])return;
      jobs[j.id]={name:j.name,status:j.status,md5b:j.md5_before,md5a:j.md5_after,url:j.url,size:j.size,dur:j.duration,err:j.error};
      if(j.status==='queued'||j.status==='processing')poll(j.id);
    });
    render();
  }).catch(()=>{});
}
</script></body></html>"""

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def sweep():
    now = time.time()
    for d in os.listdir(BASE):
        p = os.path.join(BASE, d)
        try:
            if os.path.isdir(p) and now - os.path.getmtime(p) > KEEP_HOURS * 3600:
                shutil.rmtree(p, ignore_errors=True)
                with LOCK:
                    JOBS.pop(d, None)
        except OSError:
            pass

def get_duration(path):
    r = subprocess.run(["/usr/bin/ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

def run_throttled(args, timeout=3600):
    proc = subprocess.Popen(["/usr/bin/ffmpeg", "-y"] + args,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    limiter = subprocess.Popen(["nice", "-n", "19", "cpulimit", "-l", str(CPU_LIMIT), "-p", str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill(); limiter.kill()
        return subprocess.CompletedProcess(args, 124, stderr=b"timeout")
    limiter.kill()
    return subprocess.CompletedProcess(args, proc.returncode, stderr=err)

def process_job(job):
    work = job["work"]
    src = job["src"]
    mute, trim, speed, mode = job["mute"], job["trim"], job["speed"], job["mode"]
    m1 = md5(src)
    ext = job["ext"]
    out = os.path.join(work, "cleaned" + ext)
    content_change = mute or trim > 0 or speed != 1.0
    keep_audio = job.get("keep_audio", False) and not mute
    orig_audio_path = None
    if keep_audio and not content_change:
        keep_audio = False  # 快速清洗本就流复制，音频天然保留
    if keep_audio:
        probe = subprocess.run(["/usr/bin/ffmpeg", "-i", src], capture_output=True, text=True)
        has_audio = any("Audio:" in l for l in probe.stderr.splitlines())
        if has_audio:
            orig_audio_path = os.path.join(work, "orig_audio.m4a")
            r = subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", src, "-vn",
                                "-c:a", "copy", orig_audio_path],
                               capture_output=True, timeout=1800)
            if r.returncode != 0 or not os.path.exists(orig_audio_path):
                orig_audio_path = None
    try:
        if content_change:
            args = ["-i", src]
            if trim > 0:
                dur = get_duration(src)
                if dur - 2 * trim <= 0:
                    raise RuntimeError("视频太短，掐头去尾后没内容了")
                args += ["-ss", str(trim), "-t", f"{dur - 2 * trim:.3f}"]
            vf = [f"setpts=PTS/{speed}"] if speed != 1.0 else []
            if vf:
                args += ["-vf", ",".join(vf)]
            if mute or keep_audio:
                args += ["-an"]
            args += ["-threads", "1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                     "-movflags", "+faststart", "-sn", out]
            r = run_throttled(args)
        elif mode == "deep":
            args = ["-i", src, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-c:a", "aac", "-threads", "1", "-movflags", "+faststart", out]
            if keep_audio:
                args.insert(3, "-an")
            r = run_throttled(args)
        else:
            args = ["-i", src, "-map", "0", "-c", "copy", "-map_metadata", "-1",
                    "-movflags", "+faststart", out]
            r = subprocess.run(["/usr/bin/ffmpeg", "-y"] + args, capture_output=True, timeout=1800)
        if r.returncode != 0 or not os.path.exists(out):
            raise RuntimeError((r.stderr or b"").decode(errors="ignore")[-300:] or "处理失败")
        if orig_audio_path:
            # 原音轨配回（原速不变速；-shortest 按视频长度截断对齐）
            mux_out = os.path.join(work, "muxed" + ext)
            r = subprocess.run(["/usr/bin/ffmpeg", "-y", "-i", out, "-i", orig_audio_path,
                                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
                                "-shortest", "-movflags", "+faststart", mux_out],
                               capture_output=True, timeout=1800)
            if r.returncode == 0 and os.path.exists(mux_out):
                os.replace(mux_out, out)
            os.remove(orig_audio_path)
        job["md5_before"] = m1
        job["md5_after"] = md5(out)
        job["size"] = f"{os.path.getsize(out)/1024/1024:.1f}MB"
        job["duration"] = f"{get_duration(out):.1f}s"
        job["url"] = f"/md5clean/api/download/{os.path.basename(work)}"
        job["status"] = "done"
        with open(os.path.join(work, "info.json"), "w") as fp:
            json.dump({"md5_before": m1, "md5_after": job["md5_after"], "name": job["name"]}, fp)
        os.remove(src)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)

def worker():
    while True:
        job = None
        with LOCK:
            if QUEUE:
                job = QUEUE.pop(0)
        if job:
            with LOCK:
                job["status"] = "processing"
            try:
                process_job(job)
            except Exception:
                with LOCK:
                    job["status"] = "error"; job["error"] = "内部错误"
        else:
            time.sleep(1)

threading.Thread(target=worker, daemon=True).start()

def restore_jobs_from_disk():
    """启动时扫描磁盘，恢复已完成的历史任务（文件保留 24h 内）"""
    now = time.time()
    for d in os.listdir(BASE):
        work = os.path.join(BASE, d)
        try:
            if not os.path.isdir(work) or now - os.path.getmtime(work) > KEEP_HOURS * 3600:
                continue
            ipath = os.path.join(work, "info.json")
            cleaned = [x for x in os.listdir(work) if x.startswith("cleaned")]
            if os.path.exists(ipath) and cleaned:
                info = json.load(open(ipath))
                out = os.path.join(work, cleaned[0])
                job = {
                    "id": d, "work": work, "src": "", "ext": os.path.splitext(cleaned[0])[1],
                    "name": info.get("name", d), "mode": "fast", "mute": False,
                    "keep_audio": False, "trim": 0.0, "speed": 1.0,
                    "status": "done", "md5_before": info.get("md5_before"),
                    "md5_after": info.get("md5_after"), "url": f"/md5clean/api/download/{d}",
                    "size": f"{os.path.getsize(out)/1024/1024:.1f}MB",
                    "duration": f"{get_duration(out):.1f}s",
                    "error": None, "created": os.path.getmtime(work),
                }
                JOBS[d] = job
        except Exception:
            pass

restore_jobs_from_disk()

@app.route("/md5clean/")
def index():
    return render_template_string(PAGE)

@app.route("/md5clean/api/clean", methods=["POST"])
def clean():
    sweep()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, error="未选择文件")
    work = os.path.join(BASE, uuid.uuid4().hex)
    os.makedirs(work)
    src = os.path.join(work, "src" + os.path.splitext(f.filename)[1].lower())
    f.save(src)
    if os.path.getsize(src) > MAX_SIZE:
        shutil.rmtree(work, ignore_errors=True)
        return jsonify(ok=False, error="文件超过 1GB 限制")
    job = {
        "id": os.path.basename(work),
        "work": work,
        "src": src,
        "ext": os.path.splitext(f.filename)[1].lower() or ".mp4",
        "name": f.filename,
        "mode": request.form.get("mode", "fast"),
        "mute": request.form.get("mute", "0") == "1",
        "keep_audio": request.form.get("keepaudio", "0") == "1",
        "trim": float(request.form.get("trim", "0") or 0),
        "speed": float(request.form.get("speed", "1") or 1),
        "status": "queued",
        "md5_before": None, "md5_after": None,
        "url": None, "size": None, "duration": None, "error": None,
        "created": time.time(),
    }
    with LOCK:
        JOBS[job["id"]] = job
        QUEUE.append(job)
    return jsonify(ok=True, job_id=job["id"])

@app.route("/md5clean/api/status/<jid>")
def status(jid):
    with LOCK:
        job = JOBS.get(jid)
    if not job:
        return jsonify(ok=False, error="任务不存在")
    with LOCK:
        pos = QUEUE.index(job) + 1 if job in QUEUE else 0
    return jsonify(ok=True, status=job["status"], pos=pos,
                   md5_before=job["md5_before"], md5_after=job["md5_after"],
                   url=job["url"], size=job["size"], duration=job["duration"], error=job["error"])

@app.route("/md5clean/api/list")
def job_list():
    sweep()
    with LOCK:
        jobs = [{
            "id": j["id"], "name": j["name"], "status": j["status"],
            "md5_before": j["md5_before"], "md5_after": j["md5_after"],
            "url": j["url"], "size": j["size"], "duration": j["duration"],
            "error": j["error"], "created": j["created"],
        } for j in sorted(JOBS.values(), key=lambda x: -x["created"])]
    return jsonify(ok=True, jobs=jobs)

@app.route("/md5clean/api/delete/<jid>", methods=["POST"])
def job_delete(jid):
    with LOCK:
        job = JOBS.pop(jid, None)
        if job in QUEUE:
            QUEUE.remove(job)
    if job:
        shutil.rmtree(job["work"], ignore_errors=True)
        return jsonify(ok=True)
    return jsonify(ok=False, error="任务不存在")

@app.route("/md5clean/api/download/<wid>")
def download(wid):
    work = os.path.join(BASE, wid)
    candidates = [os.path.join(work, x) for x in os.listdir(work) if x.startswith("cleaned")]
    if not candidates:
        return "文件不存在或已过期", 404
    path = candidates[0]
    name = "cleaned.mp4"
    ipath = os.path.join(work, "info.json")
    if os.path.exists(ipath):
        info = json.load(open(ipath))
        name = os.path.splitext(info.get("name", "cleaned.mp4"))[0] + "_cleaned" + os.path.splitext(path)[1]
    # 保留文件（24h 内可重复下载），由 sweep 统一清理
    return send_file(path, as_attachment=True, download_name=name)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8791, threaded=True)
