from __future__ import annotations

import html
import json
import re
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


class BilibiliSubtitleError(Exception):
    """Base error for user-facing subtitle extraction failures."""


class EmptyInputError(BilibiliSubtitleError):
    pass


class InvalidInputError(BilibiliSubtitleError):
    pass


class VideoInfoError(BilibiliSubtitleError):
    pass


class NoSubtitleError(BilibiliSubtitleError):
    pass


class SubtitleDownloadError(BilibiliSubtitleError):
    pass


CHINESE_LANG_PRIORITY = ("zh-CN", "zh-Hans", "zh", "ai-zh", "zh-Hant")
SUPPORTED_SUBTITLE_FORMATS = ("json", "vtt", "srt")
LANGUAGE_LABELS = {
    "zh-CN": "简体中文",
    "zh-Hans": "简体中文",
    "zh": "中文",
    "ai-zh": "中文字幕",
    "zh-Hant": "繁体中文",
    "en": "英文",
    "en-US": "英文",
    "en-GB": "英文",
    "ja": "日文",
    "ja-JP": "日文",
}
BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _build_headers(cookie: str | None = None) -> dict[str, str]:
    headers = dict(BILIBILI_HEADERS)
    normalized_cookie = _normalize_cookie(cookie)
    if normalized_cookie:
        headers["Cookie"] = normalized_cookie
    return headers


def _normalize_cookie(cookie: str | None) -> str:
    if not cookie:
        return ""
    cookie = cookie.strip()
    if not cookie:
        return ""

    # Browser-copied request headers are often pasted as "Cookie: ..."
    cookie = re.sub(r"^cookie\s*:\s*", "", cookie, flags=re.IGNORECASE).strip()
    return " ".join(cookie.splitlines()).strip()


def normalize_bilibili_input(url_or_bvid: str) -> str:
    value = (url_or_bvid or "").strip()
    if not value:
        raise EmptyInputError("请输入 B 站视频 URL 或 BV 号")

    bvid_match = re.search(r"(BV[0-9A-Za-z]{10})", value)
    if bvid_match and not value.lower().startswith(("http://", "https://")):
        return f"https://www.bilibili.com/video/{bvid_match.group(1)}/"

    if value.lower().startswith(("http://", "https://")):
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if not (
            hostname == "b23.tv"
            or hostname.endswith(".b23.tv")
            or hostname == "bilibili.com"
            or hostname.endswith(".bilibili.com")
        ):
            raise InvalidInputError("无法识别该输入，请检查是否为有效的 B 站视频链接或 BV 号")

        url_bvid_match = re.search(r"/video/(BV[0-9A-Za-z]{10})", parsed.path)
        if url_bvid_match:
            page_query = _extract_page_query(parsed.query)
            return f"https://www.bilibili.com/video/{url_bvid_match.group(1)}/{page_query}"
        if re.search(r"/video/(av\d+)", parsed.path, re.IGNORECASE) or hostname.endswith("b23.tv"):
            return value

    raise InvalidInputError("无法识别该输入，请检查是否为有效的 B 站视频链接或 BV 号")


def _extract_page_query(query: str) -> str:
    query_values = parse_qs(query)
    page_values = query_values.get("p")
    if not page_values:
        return ""
    try:
        page = max(1, int(page_values[-1]))
    except (TypeError, ValueError):
        return ""
    return f"?p={page}"


def get_available_subtitles(url_or_bvid: str, cookie: str | None = None) -> dict:
    url = normalize_bilibili_input(url_or_bvid)
    info = _extract_info(url, cookie)
    subtitles = _collect_subtitles(info)
    if not subtitles:
        if info.get("subtitle_login_required"):
            if cookie:
                raise NoSubtitleError("该视频没有检测到可用字幕。B 站接口仍提示字幕需要登录，请检查 Cookie 是否完整或已过期。")
            raise NoSubtitleError("该视频没有检测到可用字幕。B 站接口提示字幕需要登录，可在侧边栏粘贴 B 站 Cookie 后重试。")
        raise NoSubtitleError("该视频没有检测到可用字幕")

    return {
        "url": url,
        "video_title": info.get("title") or "bilibili_video",
        "subtitles": subtitles,
        "languages": list(subtitles.keys()),
    }


def choose_default_subtitle_lang(subtitles: dict) -> str | None:
    if not subtitles:
        return None

    normalized_lookup = {lang.lower(): lang for lang in subtitles}
    for preferred_lang in CHINESE_LANG_PRIORITY:
        matched_lang = normalized_lookup.get(preferred_lang.lower())
        if matched_lang:
            return matched_lang

    for preferred_lang in CHINESE_LANG_PRIORITY:
        preferred_lower = preferred_lang.lower()
        for lang in subtitles:
            if preferred_lower in lang.lower() or lang.lower() in preferred_lower:
                return lang

    return next(iter(subtitles), None)


def format_subtitle_language(lang: str) -> str:
    label = LANGUAGE_LABELS.get(lang) or LANGUAGE_LABELS.get(lang.lower())
    if label:
        return f"{label} ({lang})"
    if lang.lower().startswith("en"):
        return f"英文 ({lang})"
    if lang.lower().startswith("ja") or lang.lower().startswith("jp"):
        return f"日文 ({lang})"
    if lang.lower().startswith("zh"):
        return f"中文 ({lang})"
    return lang


def extract_bilibili_subtitle(url_or_bvid: str, lang: str | None = None, cookie: str | None = None) -> dict:
    url = normalize_bilibili_input(url_or_bvid)
    info = _extract_info(url, cookie)
    subtitles = _collect_subtitles(info)
    if not subtitles:
        if info.get("subtitle_login_required"):
            if cookie:
                raise NoSubtitleError("该视频没有检测到可用字幕。B 站接口仍提示字幕需要登录，请检查 Cookie 是否完整或已过期。")
            raise NoSubtitleError("该视频没有检测到可用字幕。B 站接口提示字幕需要登录，可在侧边栏粘贴 B 站 Cookie 后重试。")
        raise NoSubtitleError("该视频没有检测到可用字幕")

    selected_lang = lang or choose_default_subtitle_lang(subtitles)
    if not selected_lang or selected_lang not in subtitles:
        raise SubtitleDownloadError("字幕下载失败，请稍后重试或更换字幕语言")

    subtitle_entry = _select_subtitle_entry(subtitles[selected_lang])
    raw_subtitle = _download_subtitle(subtitle_entry, cookie)
    subtitle_format = _guess_subtitle_format(subtitle_entry, raw_subtitle)
    segments = parse_subtitle_to_segments(raw_subtitle, subtitle_format)
    if not segments:
        raise SubtitleDownloadError("字幕下载失败，请稍后重试或更换字幕语言")

    return {
        "video_title": info.get("title") or "bilibili_video",
        "language": selected_lang,
        "segments": segments,
        "last_end": segments[-1]["end"],
        "txt": segments_to_txt(segments),
        "srt": segments_to_srt(segments),
        "json": segments_to_json_text(segments),
    }


def parse_subtitle_to_segments(raw_subtitle: str, subtitle_format: str) -> list[dict]:
    subtitle_format = subtitle_format.lower().lstrip(".")
    if subtitle_format == "json":
        return _parse_bilibili_json(raw_subtitle)
    if subtitle_format == "vtt":
        return _parse_vtt(raw_subtitle)
    if subtitle_format == "srt":
        return _parse_srt(raw_subtitle)
    return _parse_bilibili_json(raw_subtitle) or _parse_vtt(raw_subtitle) or _parse_srt(raw_subtitle)


def segments_to_txt(segments: list[dict]) -> str:
    return "\n".join(_clean_text(str(segment.get("text", ""))) for segment in segments if segment.get("text"))


def segments_to_timestamped_txt(segments: list[dict]) -> str:
    lines = []
    for segment in segments:
        text = _clean_text(str(segment.get("text", "")))
        if not text:
            continue
        start = _seconds_to_display_timestamp(float(segment["start"]))
        end = _seconds_to_display_timestamp(float(segment["end"]))
        lines.append(f"[{start} - {end}] {text}")
    return "\n".join(lines)


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        start = _seconds_to_srt_timestamp(float(segment["start"]))
        end = _seconds_to_srt_timestamp(float(segment["end"]))
        text = _clean_text(str(segment.get("text", "")))
        blocks.append(f"{index}\n{start} --> {end}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def segments_to_json_text(segments: list[dict]) -> str:
    normalized_segments = [
        {
            "start": round(float(segment["start"]), 3),
            "end": round(float(segment["end"]), 3),
            "text": _clean_text(str(segment.get("text", ""))),
        }
        for segment in segments
    ]
    return json.dumps(normalized_segments, ensure_ascii=False, indent=2)


def sanitize_filename(filename: str) -> str:
    filename = re.sub(r'[\\/:*?"<>|]+', "_", filename or "bilibili_subtitle")
    filename = re.sub(r"\s+", " ", filename).strip()
    return filename[:80] or "bilibili_subtitle"


def _extract_info(url: str, cookie: str | None = None) -> dict:
    try:
        return _extract_info_from_api(url, cookie)
    except BilibiliSubtitleError:
        raise
    except Exception:
        pass

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "http_headers": _build_headers(cookie),
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
    except (DownloadError, Exception) as exc:
        if isinstance(exc, BilibiliSubtitleError):
            raise
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试") from exc

    if not isinstance(info, dict):
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")
    return info


def _extract_info_from_api(url: str, cookie: str | None = None) -> dict:
    video_query, final_url = _extract_video_query(url, cookie)
    view_info = _download_json("https://api.bilibili.com/x/web-interface/view", video_query, cookie)
    if view_info.get("code") != 0 or not isinstance(view_info.get("data"), dict):
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    video_data = view_info["data"]
    bvid = video_data.get("bvid")
    aid = video_data.get("aid")
    title = video_data.get("title") or "bilibili_video"
    pages = video_data.get("pages") or []
    part = _extract_part_number(final_url or url)

    cid = video_data.get("cid")
    if pages:
        selected_page = pages[min(part - 1, len(pages) - 1)]
        if isinstance(selected_page, dict):
            cid = selected_page.get("cid") or cid
            if part > 1 and selected_page.get("part"):
                title = f"{title} p{part:02d} {selected_page['part']}"

    if not bvid or not cid:
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    subtitles = _extract_api_subtitles(video_data.get("subtitle", {}).get("list", []))
    subtitle_login_required = False
    try:
        player_subtitle_info = _fetch_player_subtitle_info(str(bvid), str(cid), aid, cookie)
        subtitle_login_required = player_subtitle_info["need_login_subtitle"]
        subtitles = _merge_subtitles(subtitles, player_subtitle_info["subtitles"])
    except VideoInfoError:
        if not subtitles:
            raise

    return {
        "id": bvid,
        "title": title,
        "subtitles": subtitles,
        "automatic_captions": {},
        "subtitle_login_required": subtitle_login_required,
        "webpage_url": final_url or url,
    }


def _extract_info_from_webpage(url: str, cookie: str | None = None) -> dict:
    webpage, final_url = _download_text(url, return_final_url=True, cookie=cookie)
    initial_state = _extract_json_assignment(webpage, "window.__INITIAL_STATE__")
    if not isinstance(initial_state, dict):
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    if initial_state.get("error", {}).get("trueCode") in {-403, -404}:
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    video_data = initial_state.get("videoData") or initial_state.get("videoInfo") or {}
    if not isinstance(video_data, dict):
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    bvid = video_data.get("bvid")
    title = video_data.get("title") or "bilibili_video"
    aid = video_data.get("aid")
    pages = video_data.get("pages") or []
    part = _extract_part_number(final_url or url)

    cid = video_data.get("cid")
    if pages:
        selected_page = pages[min(part - 1, len(pages) - 1)]
        if isinstance(selected_page, dict):
            cid = selected_page.get("cid") or cid
            if part > 1 and selected_page.get("part"):
                title = f"{title} p{part:02d} {selected_page['part']}"

    if not bvid or not cid:
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")

    subtitles = _fetch_player_subtitles(str(bvid), str(cid), aid, cookie)
    return {
        "id": bvid,
        "title": title,
        "subtitles": subtitles,
        "automatic_captions": {},
        "webpage_url": final_url or url,
    }


def _collect_subtitles(info: dict) -> dict:
    subtitles: dict[str, list[dict[str, Any]]] = {}
    for subtitle_source in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        if not isinstance(subtitle_source, dict):
            continue
        for language, entries in subtitle_source.items():
            if not entries:
                continue
            valid_entries = [
                entry
                for entry in entries
                if isinstance(entry, dict) and (entry.get("url") or entry.get("data"))
            ]
            if valid_entries:
                subtitles.setdefault(language, []).extend(valid_entries)
    return subtitles


def _select_subtitle_entry(entries: list[dict]) -> dict:
    for preferred_format in SUPPORTED_SUBTITLE_FORMATS:
        for entry in entries:
            entry_format = str(entry.get("ext") or "").lower()
            if entry_format == preferred_format:
                return entry
    return entries[0]


def _download_subtitle(subtitle_entry: dict, cookie: str | None = None) -> str:
    if subtitle_entry.get("data"):
        return str(subtitle_entry["data"])

    subtitle_url = subtitle_entry.get("url")
    if not subtitle_url:
        raise SubtitleDownloadError("字幕下载失败，请稍后重试或更换字幕语言")

    subtitle_url = _normalize_subtitle_url(str(subtitle_url))
    request = urllib.request.Request(subtitle_url, headers=_build_headers(cookie))
    try:
        with tempfile.TemporaryDirectory():
            with urllib.request.urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SubtitleDownloadError("字幕下载失败，请稍后重试或更换字幕语言") from exc


def _download_text(
    url: str,
    return_final_url: bool = False,
    cookie: str | None = None,
) -> str | tuple[str, str]:
    request = urllib.request.Request(url, headers=_build_headers(cookie))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            if return_final_url:
                return text, response.geturl()
            return text
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试") from exc


def _download_json(url: str, query: dict[str, Any] | None = None, cookie: str | None = None) -> dict:
    if query:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(query)}"
    text = _download_text(url, cookie=cookie)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试") from exc
    if not isinstance(payload, dict):
        raise VideoInfoError("获取视频信息失败，请检查链接是否有效，或稍后重试")
    return payload


def _fetch_player_subtitles(bvid: str, cid: str, aid: Any = None, cookie: str | None = None) -> dict:
    return _fetch_player_subtitle_info(bvid, cid, aid, cookie)["subtitles"]


def _fetch_player_subtitle_info(
    bvid: str,
    cid: str,
    aid: Any = None,
    cookie: str | None = None,
) -> dict:
    query = {"cid": cid}
    if aid:
        query["aid"] = aid
    else:
        query["bvid"] = bvid

    player_info = _download_json("https://api.bilibili.com/x/player/wbi/v2", query=query, cookie=cookie)
    data = player_info.get("data", {})
    subtitle_items = (
        data
        if isinstance(data, dict)
        else {}
    ).get("subtitle", {}).get("subtitles", [])
    need_login_subtitle = bool(data.get("need_login_subtitle")) if isinstance(data, dict) else False

    subtitles = (
        _extract_api_subtitles(subtitle_items)
        if isinstance(subtitle_items, list)
        else {}
    )
    return {
        "subtitles": subtitles,
        "need_login_subtitle": need_login_subtitle,
    }


def _extract_api_subtitles(subtitle_items: Any) -> dict:
    subtitles: dict[str, list[dict[str, Any]]] = {}
    if not isinstance(subtitle_items, list):
        return subtitles

    for item in subtitle_items:
        if not isinstance(item, dict):
            continue
        language = item.get("lan")
        subtitle_url = item.get("subtitle_url")
        if not language or not subtitle_url:
            continue
        subtitles.setdefault(str(language), []).append(
            {
                "ext": "json",
                "url": _normalize_subtitle_url(str(subtitle_url)),
                "name": item.get("lan_doc") or str(language),
            }
        )
    return subtitles

def _merge_subtitles(*subtitle_dicts: dict) -> dict:
    merged: dict[str, list[dict[str, Any]]] = {}
    seen_urls: set[tuple[str, str]] = set()
    for subtitle_dict in subtitle_dicts:
        for language, entries in subtitle_dict.items():
            for entry in entries:
                key = (language, entry.get("url") or entry.get("data") or "")
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                merged.setdefault(language, []).append(entry)
    return merged


def _extract_video_query(url: str, cookie: str | None = None) -> tuple[dict[str, str], str]:
    final_url = url
    bvid_match = re.search(r"(BV[0-9A-Za-z]{10})", url)
    avid_match = re.search(r"/video/(av\d+)", url, re.IGNORECASE)

    if not bvid_match and not avid_match and "b23.tv" in (urlparse(url).hostname or ""):
        _, final_url = _download_text(url, return_final_url=True, cookie=cookie)
        bvid_match = re.search(r"(BV[0-9A-Za-z]{10})", final_url)
        avid_match = re.search(r"/video/(av\d+)", final_url, re.IGNORECASE)

    if bvid_match:
        return {"bvid": bvid_match.group(1)}, final_url
    if avid_match:
        return {"aid": avid_match.group(1)[2:]}, final_url
    raise InvalidInputError("无法识别该输入，请检查是否为有效的 B 站视频链接或 BV 号")


def _extract_json_assignment(webpage: str, assignment_name: str) -> Any:
    marker_index = webpage.find(assignment_name)
    if marker_index == -1:
        return None

    start = webpage.find("=", marker_index)
    if start == -1:
        return None
    start += 1
    while start < len(webpage) and webpage[start].isspace():
        start += 1
    if start >= len(webpage) or webpage[start] not in "{[":
        return None

    opening = webpage[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(webpage)):
        char = webpage[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return json.loads(webpage[start : index + 1])
    return None


def _extract_part_number(url: str) -> int:
    try:
        query = parse_qs(urlparse(url).query)
    except ValueError:
        return 1
    part_values = query.get("p") or ["1"]
    try:
        return max(1, int(part_values[-1]))
    except (TypeError, ValueError):
        return 1


def _normalize_subtitle_url(subtitle_url: str) -> str:
    if subtitle_url.startswith("//"):
        return f"https:{subtitle_url}"
    if subtitle_url.startswith("/"):
        return f"https://www.bilibili.com{subtitle_url}"
    return subtitle_url


def _guess_subtitle_format(subtitle_entry: dict, raw_subtitle: str) -> str:
    entry_format = str(subtitle_entry.get("ext") or "").lower().lstrip(".")
    if entry_format in SUPPORTED_SUBTITLE_FORMATS:
        return entry_format

    stripped = raw_subtitle.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    if stripped.startswith("WEBVTT"):
        return "vtt"
    if re.match(r"\d+\s*\n\d\d:\d\d:\d\d", stripped):
        return "srt"
    return entry_format or "json"


def _parse_bilibili_json(raw_subtitle: str) -> list[dict]:
    try:
        payload = json.loads(raw_subtitle)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        items = payload.get("body") or payload.get("subtitles") or payload.get("segments") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    segments = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("from", item.get("start"))
        end = item.get("to", item.get("end"))
        text = item.get("content", item.get("text", ""))
        if start is None or end is None or not text:
            continue
        segments.append({"start": float(start), "end": float(end), "text": _clean_text(str(text))})
    return segments


def _parse_vtt(raw_subtitle: str) -> list[dict]:
    segments = []
    lines = raw_subtitle.replace("\ufeff", "").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start_text, end_text = line.split("-->", 1)
        end_text = end_text.split()[0]
        text_lines = []
        index += 1
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1

        text = _clean_text("\n".join(text_lines))
        if text:
            segments.append(
                {
                    "start": _timestamp_to_seconds(start_text.strip()),
                    "end": _timestamp_to_seconds(end_text.strip()),
                    "text": text,
                }
            )
        index += 1
    return segments


def _parse_srt(raw_subtitle: str) -> list[dict]:
    normalized = raw_subtitle.replace("\ufeff", "").replace("\r\n", "\n")
    blocks = re.split(r"\n{2,}", normalized.strip())
    segments = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_text, end_text = lines[0].split("-->", 1)
        text = _clean_text("\n".join(lines[1:]))
        if text:
            segments.append(
                {
                    "start": _timestamp_to_seconds(start_text.strip()),
                    "end": _timestamp_to_seconds(end_text.strip()),
                    "text": text,
                }
            )
    return segments


def _timestamp_to_seconds(timestamp: str) -> float:
    timestamp = timestamp.replace(",", ".")
    parts = timestamp.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(parts[0])
    except (ValueError, IndexError) as exc:
        raise SubtitleDownloadError("字幕下载失败，请稍后重试或更换字幕语言") from exc


def _seconds_to_srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _seconds_to_display_timestamp(seconds: float) -> str:
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"
    return f"{minutes:02d}:{whole_seconds:02d}"


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def ensure_outputs_dir() -> Path:
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    return outputs_dir
