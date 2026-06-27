# Bilibili Subtitle Extractor

一个独立的 Streamlit 小工具，用于检测并提取 B 站单个视频已有字幕。

## 安装

```bash
cd bilibili_subtitle_tool
python -m pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

也可以使用项目内置启动命令：

```bash
./start.sh
```

macOS 可以直接双击这个文件启动：

```text
start_bilibili_subtitle.command
```

双击启动后，Streamlit 会在后台运行。即使关闭 Terminal 窗口，只要后台服务没有停止，下面这个固定链接仍然可以打开：

```text
http://localhost:8502/?ui=retro-terminal-v1
```

需要停止后台服务时，双击：

```text
stop_bilibili_subtitle.command
```

页面使用复古工作台风格。左侧登录态栏默认折叠，需要使用 Cookie 时，从页面左上角展开侧栏即可。

该启动脚本固定使用：

```text
http://localhost:8502/?ui=retro-terminal-v1
```

你可以把这个链接保存到浏览器书签。前提是本地 Streamlit 后台服务已经在运行；如果服务没运行，双击 `start_bilibili_subtitle.command` 会先重启服务，然后自动打开这个固定链接。

## 使用方式

在页面输入单个 B 站视频 URL 或 BV 号，例如：

```text
https://www.bilibili.com/video/BVxxxxxxxxxx/
https://www.bilibili.com/video/BVxxxxxxxxxx/?p=2
BVxxxxxxxxxx
```

点击“检测字幕”。如果检测到可用字幕，可以选择字幕语言，然后点击“提取字幕”。提取成功后，页面会显示字幕文本预览，并提供 `txt`、`srt`、`json` 三种下载格式。

多 P / 选集视频需要复制浏览器地址栏里的完整链接，并保留 `?p=2` 这类分集参数。只输入 BV 号时，工具会默认检测第 1 个分集。

字幕语言不限制中文。只要 B 站接口返回英文或日文 CC 字幕，例如 `en`、`en-US`、`ja`、`ja-JP`，工具会在“字幕语言”下拉框中显示并支持提取。

如果页面提示字幕需要登录，可以在侧边栏使用 Cookie 登录态：

- `粘贴临时 Cookie`：只在当前页面会话中使用。
- `保存为本机固定 Cookie`：第一次粘贴后保存到本机隐藏文件 `.bilibili_cookie`，以后启动工具可直接选择 `使用本机固定 Cookie`。
- `删除固定 Cookie`：清除本机保存的 Cookie。

## 当前功能边界

- 只支持单个视频。
- 只提取视频已有字幕。
- 不下载视频。
- 不下载音频。
- 不提取弹幕。
- 不提取评论。
- 不做合集批量处理。
- 不做 UP 主投稿批量处理。
- 不做 AI 总结。
- 不做翻译。
- 不做 Whisper / faster-whisper / ffmpeg 音频转写。
- 不使用 Selenium。
- 不使用 Playwright。
- 默认不要求用户登录 B 站。
- 支持用户手动粘贴 B 站 Cookie 作为可选登录态。
- 支持保存一个本机固定 Cookie，避免每次重复粘贴。
- 不保存用户输入历史。

## 字幕说明

当前版本只支持提取 B 站视频已经存在、且能被 `yt-dlp` 识别到的字幕。如果视频没有字幕，页面会提示：

```text
该视频没有检测到可用字幕
```

没有字幕的视频不会自动转写，也不会调用音频识别工具。

如果 B 站接口提示字幕需要登录，页面会提示你在侧边栏使用 Cookie。Cookie 失效或不完整时，仍可能检测不到字幕。

固定 Cookie 会明文保存在本工具目录的 `.bilibili_cookie` 文件里。这个文件已加入 `.gitignore`，但仍应只在你自己的电脑上使用，不要发给别人。

## 后续整合

当前项目是独立工具，不影响已有 YouTube 字幕提取工具。稳定运行后，可以把 `bilibili_subtitle.py` 作为独立模块整合进原来的 YouTube 字幕提取工具。
