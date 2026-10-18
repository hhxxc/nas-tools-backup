#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
零抓包方案：定时提醒

不碰任何接口、不需要 token，按固定时间给你发提醒邮件，
提示你去「江苏预防接种」APP 或「育苗通」手动预约。

适合：放号时间基本固定的门诊（江苏多数门诊是 工作日 7:30 / 8:00 放号）。

用法
  python reminder.py            # 常驻，到点自动发
  python reminder.py --once     # 只检查一次当前是否命中（给 cron 每分钟跑）
  python reminder.py --list     # 列出每条的提醒时间，不发信
  python reminder.py --test     # 立刻发一封测试邮件
"""

import argparse
import datetime as dt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from monitor import notify_all, log, load_config, load_state, save_state  # noqa: E402

DEFAULT_CONFIG = os.path.join(HERE, "config.json")

DAY_ALIASES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6,
}


def parse_days(days):
    """返回允许的星期集合（0=周一）。'*' / 缺省 = 每天。"""
    if not days or days == "*" or (isinstance(days, list) and "*" in days):
        return set(range(7))
    out = set()
    for d in days:
        s = str(d).strip().lower()
        if s in DAY_ALIASES:
            out.add(DAY_ALIASES[s])
        elif s.isdigit():
            n = int(s)
            out.add((n - 1) % 7 if n >= 1 else n)      # 1..7 → 0..6
    return out or set(range(7))


def parse_time(s):
    h, m = str(s).split(":")
    return int(h), int(m)


def fire_times(item, now):
    """返回 (今天的触发时刻 datetime, 允许的星期集合)"""
    h, m = parse_time(item["time"])
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return target, parse_days(item.get("days"))


def run(args):
    cfg = load_config(args.config)
    log_file = os.path.join(HERE, "reminder.log")
    state_path = os.path.join(HERE, "reminder_state.json")

    rem = cfg.get("reminders", {})
    items = rem.get("items", [])
    if not items:
        log("config.json 里没有 reminders.items，无需提醒。", log_file)
        return 2

    ncfg = cfg.get("notify", {})
    window = int(rem.get("window_seconds", 180))

    if args.test:
        log("发送测试提醒邮件 …", log_file)
        sent = notify_all(ncfg, "[测试] 定时提醒", "定时提醒通道正常，收到即可。", log_file)
        log("可用通道：%s" % (", ".join(sent) or "无"), log_file)
        return 0

    if args.list:
        now = dt.datetime.now()
        print("当前时间：%s（周%s）" % (now.strftime("%Y-%m-%d %H:%M"),
                                       "一二三四五六日"[now.weekday()]))
        for it in items:
            days = parse_days(it.get("days"))
            names = "".join("一二三四五六日"[d] for d in sorted(days))
            print("  %-5s  周[%s]  %s" % (it["time"], names, it.get("desc", "")))
        return 0

    log("定时提醒已启动：%d 条规则，轮询 20s" % len(items), log_file)
    state = load_state(state_path)

    while True:
        now = dt.datetime.now()
        today = now.strftime("%Y-%m-%d")
        for idx, it in enumerate(items):
            target, days = fire_times(it, now)
            if now.weekday() not in days:
                continue
            delta = (now - target).total_seconds()
            if not (0 <= delta < window):
                continue
            key = "%d@%s" % (idx, today)
            if state.get(key):
                continue
            title = it.get("title", "[提醒] 该去预约了")
            body = it.get("body", "请打开江苏预防接种 APP / 育苗通 手动预约。")
            log("触发提醒：%s（%s）" % (it.get("desc", ""), it["time"]), log_file)
            notify_all(ncfg, title, body, log_file)
            state[key] = time.time()
            save_state(state_path, state)
            # 清理 7 天前的记录
            for k in [k for k, v in state.items() if isinstance(v, (int, float)) and time.time() - v > 7 * 86400]:
                state.pop(k, None)
            save_state(state_path, state)

        if args.once:
            return 0
        time.sleep(20)


def main():
    ap = argparse.ArgumentParser(description="定时提醒（零抓包，不调接口）")
    ap.add_argument("-c", "--config", default=DEFAULT_CONFIG)
    ap.add_argument("--once", action="store_true", help="只检查一次（cron 每分钟跑）")
    ap.add_argument("--list", action="store_true", help="列出提醒时间")
    ap.add_argument("--test", action="store_true", help="立刻发测试邮件")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        print("找不到配置文件：%s" % args.config)
        return 2
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
