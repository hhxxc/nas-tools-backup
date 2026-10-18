#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Charles / Fiddler / Chrome 的 "Copy as cURL" 一键转成 config.json

用法
  python curl2config.py                 # 自动读剪贴板（Windows / macOS）
  python curl2config.py curl.txt        # 从文件读
  python curl2config.py --print         # 只打印结果，不写文件
  python curl2config.py -o my.json      # 写到指定文件（默认覆盖 config.json）
  python curl2config.py --name "XX门诊 儿童分时预约"

支持 Chrome/Firefox 的 bash 格式（'单引号'）、Windows cmd 格式（"双引号"）、
Charles / Fiddler 的 Copy as cURL，以及多行续行符（\\ 或 ^）。
"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 这些头由程序自己生成，不需要照抄
SKIP_HEADERS = {"host", "content-length", "accept-encoding", "connection"}

DEFAULTS = {
    "detect": {
        "type": "list_field_eq",
        "path": "data.list",
        "field": "status",
        "value": "1",
        "message_template": "{name} 有分时预约号了！请立刻打开江苏预防接种 APP 预约。（{time}）"
    },
    "context": {},
    "token_expired": {
        "keywords": ["登录超时", "请重新登录", "未登录", "会话过期", "token失效", "invalid token"],
        "code_values": ["9999", "401", "-1"],
        "code_paths": ["code"]
    },
    "interval_seconds": 60,
    "renotify_cooldown_seconds": 1800,
    "quiet_hours": ["23:00", "07:00"],
    "notify": {
        "bark": {"enabled": False, "url": "https://api.day.app/你的KEY"},
        "serverchan": {"enabled": False, "sendkey": ""},
        "pushplus": {"enabled": False, "token": ""},
        "wecom": {"enabled": False, "webhook": ""},
        "dingtalk": {"enabled": False, "webhook": "", "secret": ""},
        "email": {
            "enabled": True,
            "smtp_host": "smtp.qq.com",
            "smtp_port": 465,
            "sender": "you@qq.com",
            "password": "邮箱授权码（不是登录密码）",
            "receivers": ["you@qq.com"]
        },
        "sound": {"enabled": True}
    },
    "log_file": "monitor.log",
    "state_file": "state.json"
}


def read_clipboard():
    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                capture_output=True, text=True, timeout=15)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except Exception:  # noqa: BLE001
            pass
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=15)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout
        except Exception:  # noqa: BLE001
            pass
    return ""


def normalize(raw):
    # 去掉 cmd 的 ^ 续行 与 bash 的 \ 续行
    text = raw.replace("\r\n", "\n")
    text = re.sub(r"\^\s*\n\s*", " ", text)
    text = re.sub(r"\\\s*\n\s*", " ", text)
    # Chrome 的 --%  拼接写法
    text = text.replace("--%", " ")
    return " ".join(text.split()).strip()


def tokenize(cmd):
    # 先把 bash 的 $'...' 还原成普通引号
    cmd = re.sub(r"\$'((?:[^'\\]|\\.)*)'", lambda m: "'" + m.group(1).replace("\\'", "'") + "'", cmd)
    try:
        return shlex.split(cmd, posix=True)
    except ValueError as e:
        raise SystemExit("cURL 解析失败（引号不匹配）：%s\n请重新完整复制一遍。" % e)


def parse_curl(raw):
    text = normalize(raw)
    if not text.lower().lstrip().startswith("curl"):
        raise SystemExit("看起来不是 cURL 命令。请确认复制的是「Copy as cURL」。\n开头是：%s" % text[:60])

    tokens = tokenize(text)
    url = None
    method = None
    headers = {}
    body = None
    cookies = []

    i = 1
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None

        if t in ("-H", "--header"):
            if nxt and ":" in nxt:
                k, v = nxt.split(":", 1)
                k, v = k.strip(), v.strip()
                if k and v:
                    headers[k] = v
            i += 2
            continue
        if t in ("-X", "--request"):
            method = (nxt or "").upper()
            i += 2
            continue
        if t in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--data-ascii"):
            body = nxt if body is None else body + "&" + (nxt or "")
            if method is None:
                method = "POST"
            i += 2
            continue
        if t in ("-b", "--cookie"):
            if nxt:
                cookies.append(nxt)
            i += 2
            continue
        if t in ("-A", "--user-agent"):
            if nxt:
                headers["User-Agent"] = nxt
            i += 2
            continue
        if t in ("-e", "--referer"):
            if nxt:
                headers["Referer"] = nxt
            i += 2
            continue
        if t in ("--compressed", "-k", "--insecure", "-s", "--silent", "-L", "--location",
                 "-i", "--include", "-v", "--verbose", "--http2"):
            i += 1
            continue
        if t.startswith("-"):
            # 未知开关，若下一个不是开关则一起跳过
            i += 2 if (nxt and not nxt.startswith("-")) else 1
            continue
        if url is None and ("://" in t or t.startswith("http")):
            url = t
        i += 1

    if not url:
        raise SystemExit("没找到 URL。请确认复制完整。")
    if cookies:
        headers.setdefault("Cookie", "; ".join(cookies))
    if method is None:
        method = "GET"

    clean = {k: v for k, v in headers.items() if k.lower() not in SKIP_HEADERS}

    parsed_body = {}
    if body:
        parsed_body = body
        try:
            parsed_body = json.loads(body)
        except ValueError:
            pass

    return {"method": method, "url": url, "headers": clean, "body": parsed_body}


def main():
    ap = argparse.ArgumentParser(description="cURL → config.json")
    ap.add_argument("file", nargs="?", help="含 cURL 的文本文件；不填则读剪贴板")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "config.json"), help="输出路径")
    ap.add_argument("--name", default="江苏预防接种 · 儿童分时预约",
                    help="监控任务名称，会出现在通知标题里")
    ap.add_argument("--print", dest="do_print", action="store_true", help="只打印不写文件")
    args = ap.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = read_clipboard()
        if not raw.strip():
            raise SystemExit("剪贴板是空的。请先「Copy as cURL」，或者把 cURL 存成文件再传路径。")

    req = parse_curl(raw)

    cfg = {"name": args.name, "request": req}
    cfg.update(json.loads(json.dumps(DEFAULTS)))  # 深拷贝

    # 尽量保留原有邮箱等通知配置
    if os.path.exists(args.out):
        try:
            with open(args.out, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old.get("notify"), dict):
                for ch, val in cfg["notify"].items():
                    if ch in old["notify"] and isinstance(old["notify"][ch], dict):
                        cfg["notify"][ch].update(old["notify"][ch])
            if old.get("name") and args.name == "江苏预防接种 · 儿童分时预约":
                cfg["name"] = old["name"]
        except (ValueError, OSError):
            pass

    print("=" * 62)
    print("方法   :", req["method"])
    print("URL    :", req["url"])
    print("请求头 :")
    for k, v in req["headers"].items():
        show = v if len(v) <= 70 else v[:67] + "..."
        print("   %-18s %s" % (k, show))
    if req["body"]:
        b = req["body"] if isinstance(req["body"], str) else json.dumps(req["body"], ensure_ascii=False)
        print("请求体 :", b[:300] + ("..." if len(b) > 300 else ""))
    print("=" * 62)

    if args.do_print:
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("已写入:", args.out)
    print()
    print("下一步：")
    print("  1) 先跑  python monitor.py --once   看日志里返回的 JSON 长什么样")
    print("  2) 按实际结构改 config.json 里的 detect 判据")
    print("  3) 邮箱填好后  python monitor.py --test-notify")
    return 0


if __name__ == "__main__":
    sys.exit(main())
