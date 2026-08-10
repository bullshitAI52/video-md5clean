# 视频 MD5 清洗工具 (Video MD5 Clean)

上传视频 → 自动清洗（重新封装/重编码/变速/静音/掐头去尾/保留原声）→ MD5 变化 → 下载。
用于网盘转存去重、去水印前处理等场景。

**在线使用**：https://www.shuanghai.shop/md5clean/

## 功能

| 功能 | 说明 |
|------|------|
| 🧹 快速清洗 | ffmpeg 无损重封装（stream copy），秒级，MD5 变 |
| 🔨 深度清洗 | 重编码 H.264，MD5 必变 |
| 🔊 保留原声 | 只处理视频流，音频原样保留（原速不变速，按视频长度截断对齐） |
| 🔇 静音 | 去掉全部声音 |
| ✂️ 掐头去尾 | 删除开头/结尾指定秒数（0-60s） |
| ⚡ 变速 | 0.5~2 倍速 |
| 📦 批量处理 | 多选/拖拽/整个文件夹上传，自动排队逐个处理 |
| 💾 历史保存 | 处理结果保留 24 小时，可重复下载、可删除 |
| 🛡 CPU 限速 | ffmpeg 限速 60% + nice 降优先级，1 核小服务器不卡 |

## 部署

```bash
# 依赖
apt-get install -y ffmpeg cpulimit
uv pip install --system flask   # 或 pip install flask

# 服务
cp md5clean_server.py /root/.hermes/scripts/
cp throttle_ffmpeg.sh /root/.hermes/scripts/
```

### systemd

```ini
[Unit]
Description=Video MD5 Clean tool
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/.hermes/scripts/md5clean_server.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### nginx

```nginx
location /md5clean/ {
    proxy_pass http://127.0.0.1:8791;   # 注意：不要带尾斜杠，保留 /md5clean/ 前缀
    proxy_set_header Host $host;
    client_max_body_size 1024m;         # 上传上限 1GB
    proxy_read_timeout 1900s;
}
```

### 登录保护（可选，推荐公网部署时开启）

```bash
# 1. 生成密码文件（替换为你的账号密码）
apt-get install -y apache2-utils
htpasswd -bc /etc/nginx/.md5clean_htpasswd 你的账号 '你的密码'
chown root:www-data /etc/nginx/.md5clean_htpasswd   # 关键！nginx 需要能读到
chmod 640 /etc/nginx/.md5clean_htpasswd

# 2. nginx 加两行
# location /md5clean/ {
#     auth_basic "MD5 Clean 登录";
#     auth_basic_user_file /etc/nginx/.md5clean_htpasswd;
#     proxy_pass http://127.0.0.1:8791;
#     ...
# }
```

> ⚠️ 坑：htpasswd 文件若 chmod 600（仅 root），nginx 进程读不了会返回 500。
> 必须 chown root:www-data + chmod 640。

## 工作原理

```
上传视频
  → 任务入队（单线程队列，1 核 CPU 不互相抢）
  → ffmpeg 处理（限速 60%）
      · 快速清洗: -c copy 重封装 + 去元数据
      · 深度清洗: libx264 重编码
      · 保留原声: 先无损提取音轨 → 只处理视频 → 原音轨 -c:a copy 配回
                 （音频不变速；-shortest 按视频长度截断，音画同步）
  → 结果保留 24h，随时下载
```

## API

| 接口 | 说明 |
|------|------|
| `POST /md5clean/api/clean` | 上传处理（multipart: file + mode/mute/keepaudio/trim/speed） |
| `GET /md5clean/api/status/<id>` | 任务状态（queued/processing/done/error） |
| `GET /md5clean/api/list` | 历史任务列表 |
| `POST /md5clean/api/delete/<id>` | 删除任务及文件 |
| `GET /md5clean/api/download/<id>` | 下载处理结果 |

## 注意

- 上传上限 1GB/个；文件 24 小时后自动清理
- 变速会裁掉音乐结尾（音乐原速，画面变速变短）；不想裁音乐就别变速
- 服务器内存 1GB 时深度清洗大文件较慢（限速的代价）
