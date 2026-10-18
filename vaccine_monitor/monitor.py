#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
江苏预防接种 APP —— 余号监控 / 到号提醒（通用轮询框架）

设计原则
  * 只做「监控 + 提醒」，不自动预约、不绕过风控；
  * 零第三方依赖（全部标准库），Windows / Linux / NAS 都能直接跑；
  * 所有可变项都在 config.json，换新 token 只改配置、不动代码；
  * 自带登录态失效检测：token 过期会主动提醒你重新抓包。

用法
  python monitor.py                  # 常驻轮询
  python monitor.py --once           # 只查一次（放进 cron / 计划任务）
  python monitor.py --test-notify    # 只测通知通道是否通
  python monitor.py -c other.json    # 指定配置文件
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "config.json")
UA = ("Mozilla/5.0 (Linux; Android 13; V2227A Build/TP1A.220624.014) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
      "Chrome/118.0.0.0 Mobile Safari/537.36")

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def log(msg, log_file=None):
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def http(method, url, headers=None, params=None, body=None, timeout=20):
    """返回 (status_code, text)。status_code 为 0 表示网络层失败。"""
    if params:
        sep = "&" if ("?" in url) else "?"
        url = url + sep + urllib.parse.urlencode(params)
    data = None
    hdr = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    if headers:
        hdr.update(headers)
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            hdr.setdefault("Content-Type", "application/json")
        else:
            data = str(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdr, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, "%s: %s" % (type(e).__name__, e)


def dig(obj, path):
    """按 'a.b.c' 或 'a.0.b' 取值，取不到返回 None。"""
    if not path:
        return obj
    for key in str(path).split("."):
        if isinstance(obj, list):
            if not key.lstrip("-").isdigit():
                return None
            idx = int(key)
            if -len(obj) <= idx < len(obj):
                obj = obj[idx]
            else:
                return None
        elif isinstance(obj, dict):
            if key not in obj:
                return None
            obj = obj[key]
        else:
            return None
    return obj


def as_number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# 判据：从响应里判断「有没有号」
# --------------------------------------------------------------------------- #
def run_detector(det, text):
    """
    返回 (hit: bool, detail: str)
    det.type 支持：
      json_path_eq      某路径的值 == value        （如 code、"hasNumber"）
      json_path_gt      某路径的值 >  value        （如剩余数量）
      json_path_true    某路径为真
      list_field_eq     路径取到列表，存在 item[field] == value
      list_field_gt     路径取到列表，存在 item[field] >  value
      list_count_gt     路径取到列表，元素个数 > value
      contains          响应文本包含 substring
      regex             响应文本匹配正则
    """
    dtype = det.get("type")

    if dtype in ("contains", "regex"):
        if dtype == "contains":
            hit = str(det.get("substring", "")) in text
        else:
            hit = re.search(str(det.get("pattern", "")), text) is not None
        return hit, ("文本命中" if hit else "文本未命中")

    try:
        obj = json.loads(text)
    except ValueError:
        return False, "响应不是合法 JSON（可能被风控/需登录）"

    if dtype == "json_path_eq":
        cur = dig(obj, det["path"])
        hit = str(cur) == str(det.get("value"))
        return hit, "path=%s 实际=%r 期望=%r" % (det["path"], cur, det.get("value"))

    if dtype == "json_path_gt":
        cur = as_number(dig(obj, det["path"]))
        thr = as_number(det.get("value"))
        hit = cur is not None and thr is not None and cur > thr
        return hit, "path=%s 实际=%r 阈值 %r" % (det["path"], cur, thr)

    if dtype == "json_path_true":
        cur = dig(obj, det["path"])
        hit = cur is True or str(cur).lower() in ("true", "1")
        return hit, "path=%s 实际=%r" % (det["path"], cur)

    if dtype in ("list_field_eq", "list_field_gt", "list_count_gt"):
        items = dig(obj, det["path"])
        if not isinstance(items, list):
            return False, "path=%s 不是列表（%s）" % (det["path"], type(items).__name__)
        if dtype == "list_count_gt":
            thr = as_number(det.get("value")) or 0
            hit = len(items) > thr
            return hit, "列表长度 %d，阈值 %g" % (len(items), thr)
        field = det.get("field")
        if dtype == "list_field_eq":
            matched = [x for x in items if isinstance(x, dict) and str(x.get(field)) == str(det.get("value"))]
            return bool(matched), "匹配 %d 条（%s == %r）" % (len(matched), field, det.get("value"))
        thr = as_number(det.get("value"))
        matched = []
        for x in items:
            if not isinstance(x, dict):
                continue
            n = as_number(x.get(field))
            if n is not None and thr is not None and n > thr:
                matched.append(x)
        return bool(matched), "匹配 %d 条（%s > %r）" % (len(matched), field, det.get("value"))

    return False, "未知判据类型：%s" % dtype


def check_expired(rule, text, status):
    """登录态 / 会话失效检测。返回 (expired: bool, reason: str)"""
    if not rule:
        return False, ""
    if status in (401, 403):
        return True, "HTTP %d" % status
    for kw in rule.get("keywords", []):
        if kw and kw in text:
            return True, "响应含关键词「%s」" % kw
    codes = [str(c) for c in rule.get("code_values", [])]
    if codes:
        try:
            obj = json.loads(text)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            for cp in rule.get("code_paths", ["code"]):
                cur = dig(obj, cp)
                if cur is not None and str(cur) in codes:
                    return True, "code=%s" % cur
            msg = str(obj.get("msg", "")) + str(obj.get("message", ""))
            for kw in rule.get("keywords", []):
                if kw and kw in msg:
                    return True, "msg 含「%s」" % kw
    return False, ""


# --------------------------------------------------------------------------- #
# 通知通道
# --------------------------------------------------------------------------- #
def notify_bark(cfg, title, body):
    url = str(cfg["url"]).rstrip("/")
    path = "%s/%s/%s" % (url, urllib.parse.quote(title), urllib.parse.quote(body))
    st, txt = http("GET", path, timeout=15)
    return st == 200, "bark http=%s" % st


def notify_serverchan(cfg, title, body):
    sendkey = cfg.get("sendkey", "")
    st, txt = http("POST", "https://sctapi.ftqq.com/%s.send" % sendkey,
                   body={"title": title, "desp": body}, timeout=15)
    ok = st == 200 and '"code":0' in txt.replace(" ", "")
    return ok, "serverchan http=%s" % st


def notify_pushplus(cfg, title, body):
    st, txt = http("POST", "https://www.pushplus.plus/send",
                   body={"token": cfg.get("token", ""), "title": title, "content": body}, timeout=15)
    return st == 200, "pushplus http=%s" % st


def notify_wecom(cfg, title, body):
    st, txt = http("POST", cfg.get("webhook", ""),
                   body={"msgtype": "text", "text": {"content": "%s\n%s" % (title, body)}}, timeout=15)
    return st == 200, "wecom http=%s" % st


def notify_dingtalk(cfg, title, body):
    url = cfg.get("webhook", "")
    secret = cfg.get("secret", "")
    if secret:
        ts = str(round(time.time() * 1000))
        raw = "%s\n%s" % (ts, secret)
        sig = urllib.parse.quote_plus(
            base64.b64encode(hmac.new(secret.encode("utf-8"), raw.encode("utf-8"),
                                      hashlib.sha1).digest()))
        url = "%s&timestamp=%s&sign=%s" % (url, ts, sig)
    st, txt = http("POST", url, body={"msgtype": "text",
                                      "text": {"content": "%s\n%s" % (title, body)}}, timeout=15)
    return st == 200, "dingtalk http=%s" % st


def notify_email(cfg, title, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = Header(cfg.get("sender", ""), "utf-8")
    msg["To"] = Header(",".join(cfg.get("receivers", [])), "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    host = cfg.get("smtp_host", "smtp.qq.com")
    port = int(cfg.get("smtp_port", 465))
    srv = smtplib.SMTP_SSL(host, port, timeout=20, context=_SSL_CTX)
    try:
        srv.login(cfg.get("sender", ""), cfg.get("password", ""))
        srv.sendmail(cfg.get("sender", ""), cfg.get("receivers", []), msg.as_string())
    finally:
        try:
            srv.quit()
        except Exception:  # noqa: BLE001
            pass
    return True, "email sent"


def notify_sound(cfg, title, body):
    text = "%s。%s" % (title, body)
    try:
        if sys.platform.startswith("win"):
            import winsound
            for _ in range(3):
                winsound.Beep(880, 400)
                winsound.Beep(660, 400)
            return True, "windows beep"
        if sys.platform == "darwin":
            os.system("say %s" % json.dumps(text, ensure_ascii=False))
            return True, "mac say"
        print("\a", end="", flush=True)
        return True, "linux bell"
    except Exception as e:  # noqa: BLE001
        return False, "sound failed: %s" % e


CHANNELS = {
    "bark": notify_bark,
    "serverchan": notify_serverchan,
    "pushplus": notify_pushplus,
    "wecom": notify_wecom,
    "dingtalk": notify_dingtalk,
    "email": notify_email,
    "sound": notify_sound,
}


def notify_all(ncfg, title, body, log_file=None):
    sent = []
    for name, ch in CHANNELS.items():
        conf = ncfg.get(name)
        if not isinstance(conf, dict) or not conf.get("enabled"):
            continue
        try:
            ok, info = ch(conf, title, body)
        except Exception as e:  # noqa: BLE001
            ok, info = False, "%s: %s" % (type(e).__name__, e)
        log("  通知[%s] %s (%s)" % (name, "成功" if ok else "失败", info), log_file)
        if ok:
            sent.append(name)
    return sent


# --------------------------------------------------------------------------- #
# 状态（去重 / 冷却）
# --------------------------------------------------------------------------- #
def load_state(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def in_quiet_hours(qh, now=None):
    if not qh or len(qh) != 2:
        return False
    now = now or datetime.now()
    cur = now.strftime("%H:%M")
    start, end = qh[0], qh[1]
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end          # 跨零点


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def do_check(cfg, log_file):
    """执行一次请求 + 判据。返回 (ok, expired, hit, detail, text)"""
    req = cfg["request"]
    status, text = http(req.get("method", "GET"), req["url"],
                        headers=req.get("headers"), params=req.get("params"),
                        body=req.get("body"))
    if status == 0:
        return False, False, False, "网络错误：%s" % text[:120], ""
    expired, why = check_expired(cfg.get("token_expired"), text, status)
    if expired:
        return True, True, False, why, text
    hit, detail = run_detector(cfg["detect"], text)
    return True, False, hit, detail, text


def build_message(cfg, text):
    tpl = cfg["detect"].get("message_template", "目标状态已满足")
    ctx = dict(cfg.get("context", {}))
    try:
        ctx.setdefault("time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ctx.setdefault("name", cfg.get("name", "监控任务"))
        return tpl.format(**ctx)
    except (KeyError, IndexError, ValueError):
        return tpl


def run(cfg, cfg_path, once=False, test_notify=False):
    log_file = cfg.get("log_file") or os.path.join(HERE, "monitor.log")
    if log_file and not os.path.isabs(log_file):
        log_file = os.path.join(HERE, log_file)
    state_path = cfg.get("state_file") or os.path.join(HERE, "state.json")
    if not os.path.isabs(state_path):
        state_path = os.path.join(HERE, state_path)

    name = cfg.get("name", "监控任务")
    interval = int(cfg.get("interval_seconds", 60))
    cooldown = int(cfg.get("renotify_cooldown_seconds", 1800))
    quiet = cfg.get("quiet_hours")
    ncfg = cfg.get("notify", {})

    if test_notify:
        log("发送测试通知 …", log_file)
        sent = notify_all(ncfg, "[测试] %s" % name,
                          "这是一条测试消息，收到即代表通知通道配置正确。", log_file)
        log("可用通道：%s" % (", ".join(sent) or "无"), log_file)
        return 0

    log("启动监控：%s（间隔 %ds，安静时段 %s）" % (name, interval, quiet or "无"), log_file)
    state = load_state(state_path)
    round_no = 0

    while True:
        round_no += 1
        try:
            ok, expired, hit, detail, text = do_check(cfg, log_file)
        except Exception as e:  # noqa: BLE001
            ok, expired, hit, detail = False, False, False, "异常：%s" % e

        if not ok:
            log("第 %d 轮：%s" % (round_no, detail), log_file)
        elif expired:
            log("第 %d 轮：登录态失效（%s）" % (round_no, detail), log_file)
            if not in_quiet_hours(quiet):
                notify_all(ncfg, "[需处理] %s 登录态已失效" % name,
                           "监控无法继续，请重新抓包并更新 config.json 里的 token / 请求头。\n原因：%s" % detail,
                           log_file)
            # 失效后拉长间隔，避免无意义刷请求
            time.sleep(max(interval, 600))
            continue
        else:
            log("第 %d 轮：%s" % (round_no, "★ 有号！" if hit else "暂无号") + " | " + detail, log_file)
            if hit:
                body = build_message(cfg, text)
                last = state.get("last_sign")
                last_ts = state.get("last_ts", 0)
                same = (last == detail) and (time.time() - last_ts < cooldown)
                if same:
                    log("  与上次命中一致且在冷却期内，跳过通知", log_file)
                else:
                    if in_quiet_hours(quiet):
                        log("  处于安静时段，仅记录不通知", log_file)
                    else:
                        notify_all(ncfg, "[有号] %s" % name, body, log_file)
                    state["last_sign"] = detail
                    state["last_ts"] = time.time()
                    state["last_body"] = body
                    save_state(state_path, state)
            elif state.get("last_sign"):
                # 号没了，清空去重标记，下次放号可以立刻再提醒
                state.pop("last_sign", None)
                save_state(state_path, state)

        if once:
            return 0
        time.sleep(max(5, interval))


def main():
    ap = argparse.ArgumentParser(description="江苏预防接种 APP 余号监控提醒（只监控不抢号）")
    ap.add_argument("-c", "--config", default=DEFAULT_CONFIG, help="配置文件路径")
    ap.add_argument("--once", action="store_true", help="只检查一次后退出（适合 cron）")
    ap.add_argument("--test-notify", action="store_true", help="只测通知通道")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        print("找不到配置文件：%s\n请先复制 config.example.json 为 config.json 并按 README 填写。"
              % args.config)
        return 2
    cfg = load_config(args.config)
    return run(cfg, args.config, once=args.once, test_notify=args.test_notify)


if __name__ == "__main__":
    sys.exit(main())
