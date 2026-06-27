from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from bilibili_subtitle import (
    BilibiliSubtitleError,
    EmptyInputError,
    InvalidInputError,
    NoSubtitleError,
    SubtitleDownloadError,
    VideoInfoError,
    choose_default_subtitle_lang,
    extract_bilibili_subtitle,
    format_subtitle_language,
    get_available_subtitles,
    sanitize_filename,
    segments_to_timestamped_txt,
)


COOKIE_FILE = Path(__file__).resolve().parent / ".bilibili_cookie"


def load_saved_cookie() -> str:
    if not COOKIE_FILE.exists():
        return ""
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def save_cookie(cookie: str) -> None:
    COOKIE_FILE.write_text(cookie.strip(), encoding="utf-8")


def delete_saved_cookie() -> None:
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()


def render_copy_button(text: str) -> None:
    payload = json_escape(text)
    components.html(
        f"""
        <button id="copy-subtitle-text" class="copy-button" type="button">复制当前文本</button>
        <span id="copy-subtitle-status" class="copy-status"></span>
        <script>
        const button = document.getElementById("copy-subtitle-text");
        const status = document.getElementById("copy-subtitle-status");
        const text = {payload};

        async function copyText() {{
          try {{
            await navigator.clipboard.writeText(text);
            status.textContent = "已复制";
          }} catch (error) {{
            const textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.left = "-9999px";
            document.body.appendChild(textarea);
            textarea.focus();
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);
            status.textContent = "已复制";
          }}
          window.setTimeout(() => {{
            status.textContent = "";
          }}, 1800);
        }}

        button.addEventListener("click", copyText);
        </script>
        <style>
        .copy-button {{
          border: 1px solid oklch(0.675 0.155 113);
          background: oklch(0.675 0.155 113);
          color: oklch(0.090 0.010 112);
          border-radius: 8px;
          padding: 0.55rem 0.8rem;
          font: 700 0.92rem ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          cursor: pointer;
        }}
        .copy-button:hover {{
          background: oklch(0.765 0.150 113);
          border-color: oklch(0.765 0.150 113);
        }}
        .copy-button:focus-visible {{
          outline: 2px solid oklch(0.820 0.155 113);
          outline-offset: 2px;
        }}
        .copy-status {{
          color: oklch(0.925 0.018 112);
          margin-left: 0.65rem;
          font: 0.92rem ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
        </style>
        """,
        height=48,
    )


def json_escape(text: str) -> str:
    import json

    return json.dumps(text, ensure_ascii=False)


st.set_page_config(
    page_title="Bilibili Subtitle Extractor",
    page_icon="📺",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def inject_retro_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: oklch(0.145 0.018 112);
            --surface: oklch(0.205 0.026 112);
            --surface-2: oklch(0.255 0.032 112);
            --ink: oklch(0.925 0.018 112);
            --muted: oklch(0.735 0.030 112);
            --primary: oklch(0.765 0.150 113);
            --primary-strong: oklch(0.675 0.155 113);
            --accent: oklch(0.735 0.150 61);
            --danger: oklch(0.650 0.175 28);
            --line: oklch(0.410 0.055 112);
            --focus: oklch(0.820 0.155 113);
        }

        .stApp {
            background:
                linear-gradient(180deg, oklch(0.170 0.022 112), var(--bg) 42%),
                var(--bg);
            color: var(--ink);
        }

        .block-container {
            max-width: 920px;
            padding-top: 3rem;
            padding-bottom: 3rem;
        }

        [data-testid="stSidebar"] {
            background: oklch(0.120 0.018 112);
            border-right: 1px solid var(--line);
        }

        [data-testid="stSidebar"] * {
            color: var(--ink);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {
            color: var(--muted);
        }

        .retro-shell {
            border: 1px solid var(--line);
            background: var(--surface);
            border-radius: 10px;
            padding: 1.35rem 1.45rem;
        }

        .retro-kicker {
            color: var(--primary);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.78rem;
            margin: 0 0 0.45rem;
        }

        .retro-title {
            color: var(--ink);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 2rem;
            line-height: 1.12;
            letter-spacing: 0;
            margin: 0;
            text-wrap: balance;
        }

        .retro-subtitle {
            color: var(--muted);
            font-size: 0.98rem;
            line-height: 1.65;
            max-width: 66ch;
            margin: 0.75rem 0 0;
            text-wrap: pretty;
        }

        h1, h2, h3, h4,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--ink);
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            letter-spacing: 0;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stText"],
        label,
        .stTextArea textarea,
        .stTextInput input {
            color: var(--ink);
        }

        .stTextInput input,
        .stTextArea textarea,
        [data-baseweb="select"] > div {
            background: oklch(0.130 0.016 112) !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px !important;
            color: var(--ink) !important;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }

        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: oklch(0.690 0.030 112) !important;
            opacity: 1 !important;
        }

        .stTextInput input:focus,
        .stTextArea textarea:focus {
            border-color: var(--focus) !important;
            box-shadow: 0 0 0 2px oklch(0.765 0.150 113 / 0.25) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border: 1px solid var(--primary-strong) !important;
            background: var(--primary-strong) !important;
            color: oklch(0.090 0.010 112) !important;
            border-radius: 8px !important;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-weight: 700 !important;
            transition: transform 160ms ease, background-color 160ms ease, border-color 160ms ease;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: var(--primary) !important;
            border-color: var(--primary) !important;
            transform: translateY(-1px);
        }

        .stButton > button:focus-visible,
        .stDownloadButton > button:focus-visible {
            outline: 2px solid var(--focus) !important;
            outline-offset: 2px !important;
        }

        [data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid var(--line);
            background: var(--surface-2);
            color: var(--ink);
        }

        [data-testid="stAlert"] p {
            color: var(--ink);
        }

        div[data-testid="stCheckbox"] label,
        div[data-testid="stRadio"] label {
            color: var(--ink);
        }

        [data-testid="stTextArea"] textarea {
            min-height: 320px;
            line-height: 1.55;
            overflow-y: scroll !important;
            scrollbar-width: auto;
            scrollbar-color: var(--primary-strong) oklch(0.130 0.016 112);
        }

        [data-testid="stTextArea"] textarea::-webkit-scrollbar {
            width: 14px;
        }

        [data-testid="stTextArea"] textarea::-webkit-scrollbar-track {
            background: oklch(0.130 0.016 112);
            border-left: 1px solid var(--line);
        }

        [data-testid="stTextArea"] textarea::-webkit-scrollbar-thumb {
            background: var(--primary-strong);
            border: 3px solid oklch(0.130 0.016 112);
            border-radius: 8px;
        }

        [data-testid="stTextArea"] textarea::-webkit-scrollbar-thumb:hover {
            background: var(--primary);
        }

        hr {
            border-color: var(--line);
        }

        @media (prefers-reduced-motion: reduce) {
            .stButton > button,
            .stDownloadButton > button {
                transition: none;
            }

            .stButton > button:hover,
            .stDownloadButton > button:hover {
                transform: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_retro_styles()

st.markdown(
    """
    <section class="retro-shell">
      <p class="retro-kicker">LOCAL SUBTITLE TERMINAL / BILIBILI</p>
      <h1 class="retro-title">Bilibili Subtitle Extractor</h1>
      <p class="retro-subtitle">输入单个 B 站视频链接或 BV 号，检测已有 CC 字幕，选择语言后导出 TXT、SRT 或 JSON。</p>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("登录态")
    saved_cookie = load_saved_cookie()
    cookie_mode = st.radio(
        "Cookie 使用方式",
        ("不使用登录态", "使用本机固定 Cookie", "粘贴临时 Cookie"),
        index=1 if saved_cookie else 0,
    )
    bili_cookie = ""

    if cookie_mode == "使用本机固定 Cookie":
        if saved_cookie:
            bili_cookie = saved_cookie
            st.success("已加载本机固定 Cookie")
            if st.button("删除固定 Cookie"):
                delete_saved_cookie()
                st.session_state.subtitle_info = None
                st.session_state.subtitle_result = None
                st.rerun()
        else:
            st.info("还没有保存固定 Cookie。请先切换到“粘贴临时 Cookie”并保存。")
    elif cookie_mode == "粘贴临时 Cookie":
        bili_cookie = st.text_input(
            "B 站 Cookie",
            type="password",
            placeholder="粘贴浏览器请求头里的 Cookie",
        )
        st.caption("直接使用时只在当前页面会话生效；保存后会写入本机隐藏文件。请勿粘贴账号密码。")
        if st.button("保存为本机固定 Cookie"):
            if bili_cookie.strip():
                save_cookie(bili_cookie)
                st.success("已保存固定 Cookie")
                st.rerun()
            else:
                st.warning("请先粘贴 Cookie")


def show_error(error: Exception) -> None:
    if isinstance(error, EmptyInputError):
        st.warning("请输入 B 站视频 URL 或 BV 号")
    elif isinstance(error, InvalidInputError):
        st.error("无法识别该输入，请检查是否为有效的 B 站视频链接或 BV 号")
    elif isinstance(error, VideoInfoError):
        st.error("获取视频信息失败，请检查链接是否有效，或稍后重试")
    elif isinstance(error, NoSubtitleError):
        st.info(str(error) or "该视频没有检测到可用字幕")
    elif isinstance(error, SubtitleDownloadError):
        st.error("字幕下载失败，请稍后重试或更换字幕语言")
    else:
        st.error("处理失败，请稍后重试")


if "subtitle_info" not in st.session_state:
    st.session_state.subtitle_info = None
if "subtitle_result" not in st.session_state:
    st.session_state.subtitle_result = None
if "last_input" not in st.session_state:
    st.session_state.last_input = ""
if "last_cookie" not in st.session_state:
    st.session_state.last_cookie = ""


video_input = st.text_input("B 站视频 URL 或 BV 号", placeholder="例如：https://www.bilibili.com/video/BV...?p=2 或 BV...")
st.caption("多 P / 选集视频请复制浏览器地址栏里的完整链接，保留 `?p=2` 这类分集参数；只输入 BV 号会默认检测第 1 个分集。")

if st.button("检测字幕", type="primary"):
    st.session_state.subtitle_info = None
    st.session_state.subtitle_result = None
    st.session_state.last_input = video_input
    st.session_state.last_cookie = bili_cookie
    try:
        with st.spinner("正在检测字幕..."):
            st.session_state.subtitle_info = get_available_subtitles(video_input, st.session_state.last_cookie)
    except BilibiliSubtitleError as error:
        show_error(error)
    except Exception as error:
        show_error(error)


subtitle_info = st.session_state.subtitle_info
if subtitle_info:
    st.success(f"检测到可用字幕：{subtitle_info['video_title']}")

    subtitles = subtitle_info["subtitles"]
    languages = subtitle_info["languages"]
    default_lang = choose_default_subtitle_lang(subtitles)
    default_index = languages.index(default_lang) if default_lang in languages else 0

    selected_lang = st.selectbox(
        "字幕语言",
        languages,
        index=default_index,
        format_func=format_subtitle_language,
    )

    if st.button("提取字幕"):
        try:
            with st.spinner("正在提取字幕..."):
                st.session_state.subtitle_result = extract_bilibili_subtitle(
                    st.session_state.last_input,
                    selected_lang,
                    st.session_state.last_cookie,
                )
        except BilibiliSubtitleError as error:
            show_error(error)
        except Exception as error:
            show_error(error)

    result = st.session_state.subtitle_result
    if result and result["language"] != selected_lang:
        result = None
    if result:
        st.subheader("字幕文本预览")
        show_timestamps = st.checkbox("显示时间戳")
        preview_source = (
            segments_to_timestamped_txt(result["segments"])
            if show_timestamps
            else result["txt"]
        )
        st.caption(
            f"共 {len(result['segments'])} 段，{len(preview_source)} 个字符，"
            f"最后字幕时间 {int(round(result['last_end']))} 秒。预览框显示完整文本。"
        )
        st.text_area("预览", preview_source, height=460, label_visibility="collapsed")
        render_copy_button(preview_source)

        filename_base = sanitize_filename(result["video_title"])
        st.download_button(
            "下载 TXT",
            data=result["txt"],
            file_name=f"{filename_base}_{result['language']}.txt",
            mime="text/plain",
        )
        st.download_button(
            "下载 SRT",
            data=result["srt"],
            file_name=f"{filename_base}_{result['language']}.srt",
            mime="text/plain",
        )
        st.download_button(
            "下载 JSON",
            data=result["json"],
            file_name=f"{filename_base}_{result['language']}.json",
            mime="application/json",
        )
