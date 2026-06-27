# Bilibili Subtitle Extractor

一个独立的 Streamlit 小工具，用于检测并提取 B 站单个视频已有字幕。

## 功能

- 支持输入 B 站视频 URL 或 BV 号。
- 支持单个视频字幕检测和提取。
- 支持多 P / 选集视频，输入完整链接并保留 `?p=2` 这类分集参数即可。
- 支持选择 B 站接口返回的字幕语言，包括中文、英文、日文等已有 CC 字幕。
- 支持字幕文本预览。
- 支持显示 / 隐藏时间戳。
- 支持复制当前预览文本。
- 支持下载 `txt`、`srt`、`json` 三种格式。
- 支持可选 B 站 Cookie 登录态，用于访问需要登录后才返回的字幕。

## 安装

```bash
python -m pip install -r requirements.txt
```

## 运行

```bash
streamlit run app.py
```

启动后浏览器会打开本地页面。如果没有自动打开，可以手动访问终端里显示的地址，通常类似：

```text
http://localhost:8501
```

## 使用方式

输入单个 B 站视频 URL 或 BV 号，例如：

```text
https://www.bilibili.com/video/BVxxxxxxxxxx/
https://www.bilibili.com/video/BVxxxxxxxxxx/?p=2
BVxxxxxxxxxx
```

点击“检测字幕”。如果检测到可用字幕，选择字幕语言，然后点击“提取字幕”。

多 P / 选集视频请复制浏览器地址栏里的完整链接，并保留 `?p=2` 这类分集参数。只输入 BV 号时，工具默认检测第 1 个分集。

## Cookie 登录态

部分 B 站字幕需要登录后才会通过接口返回。遇到这种情况时，可以在侧边栏使用 Cookie：

- `粘贴临时 Cookie`：只在当前页面会话中使用。
- `保存为本机固定 Cookie`：保存到本机隐藏文件 `.bilibili_cookie`，以后可以直接使用。
- `删除固定 Cookie`：删除本机保存的 Cookie。

`.bilibili_cookie` 已加入 `.gitignore`，不要把它提交或发给别人。

## 功能边界

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

## 字幕说明

当前版本只支持提取 B 站视频已经存在、且能被 B 站接口返回的字幕。

如果视频没有字幕，页面会提示：

```text
该视频没有检测到可用字幕
```

没有字幕的视频不会自动转写，也不会调用音频识别工具。
