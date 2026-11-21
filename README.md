# 听读 · 边看边听

自用的网页阅读器（PWA，纯静态、零依赖）。灵感来自「微信读书」的听书 + 「Readest」的朗读跟随，做了最常用的那部分：

- **边看边听**：正文逐句高亮跟随，点任意一句从那里开始听
- **两种声音**：章节带预生成音频（高质量神经网络音色）时播音频；没有音频时用手机自带朗读
- 倍速 0.8–2.5x、定时关闭（含「本章结束」）、±15 秒、上/下一章、锁屏控制（Media Session）
- 自动续读：记住每本书读到哪一章哪一句
- 三套主题（纸张/护眼/夜间）、字号、行距
- 导入本地 TXT（自动识别 UTF-8 / GBK，自动分章分句）
- 可「添加到主屏幕」当 App 用（iOS Safari / Android Chrome）

## 使用
打开页面 → 右上「＋ 导入 TXT」，或页脚「连接私人书库」粘贴书库地址。

书库格式（任何静态服务器都行）：
```
<库地址>/index.json                    [{id,title,author,chapters,audio}]
<库地址>/<id>/book.json                {title,author,chapters:[{title,paras:[[句,句],..],audio?,times?}]}
<库地址>/<id>/chNN.mp3                 章节音频（times 为每句起始毫秒）
```
通过 `?lib=<库地址>` 链接可一次性连接（连接后自动写入本机）。

## 工具（tools/）
- `make_audio.py`：章节 JSON → 句级时间轴 + 每章 mp3（edge-tts 合成，可断点续跑）
- `ocr_vision.swift` + `extract_ocr.py`：扫描版 PDF → macOS Vision OCR → 按书签切章
- `serve_private.py`：带令牌、支持 Range 的私人书库静态服务

## 版权
本仓库只含阅读器代码，不含任何书籍内容。书库请自行放在私有地址。
