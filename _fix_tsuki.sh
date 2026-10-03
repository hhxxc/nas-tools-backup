#!/bin/bash
# 修复: Tsuki.ga.Michibiku.Isekai.Douchuu.S02E25 被误识别为 ゆがんだ月(1959) 的硬链接
# 用法: 在 NAS 上执行 bash _fix_tsuki.sh

DB=/volume2/docker/nastool/config/user.db
NASTOOL_URL=http://127.0.0.1:3000
API_KEY=""

echo "===== 1. 查找错误转移记录 ====="
# 查询 TRANSFER_HISTORY 中 TITLE 包含 ゆがんだ月 的记录
python3 - <<'PY'
import sqlite3, json
con = sqlite3.connect(f'file:{__import__("os").environ.get("DB","/volume2/docker/nastool/config/user.db")}?mode=ro', uri=True)
rows = con.execute("""
    SELECT ID, TITLE, YEAR, TYPE, CATEGORY, SEASON_EPISODE,
           SOURCE_PATH, SOURCE_FILENAME,
           DEST, DEST_PATH, DEST_FILENAME
    FROM TRANSFER_HISTORY
    WHERE TITLE LIKE '%ゆがんだ%'
       OR SOURCE_FILENAME LIKE '%Tsuki%Michibiku%'
       OR DEST_FILENAME LIKE '%ゆがんだ%'
    ORDER BY ID DESC
""").fetchall()
con.close()
if not rows:
    print("  未找到匹配记录！")
    exit(0)
for r in rows:
    print(f"  ID={r[0]} | {r[1]} ({r[2]}) | {r[3]} | {r[4]}")
    print(f"    SOURCE: {r[6]}/{r[7]}")
    print(f"    DEST:   {r[9]}/{r[10]}")
    print()

# 输出第一条记录的信息供后续使用
r = rows[0]
info = {
    "logid": r[0],
    "title": r[1],
    "source_path": r[6],
    "source_filename": r[7],
    "dest": r[8],
    "dest_path": r[9],
    "dest_filename": r[10],
    "mode": "link"
}
# 写入临时文件
with open("/tmp/_fix_tsuki_info.json", "w") as f:
    json.dump(info, f, ensure_ascii=False)
print("  => 信息已写入 /tmp/_fix_tsuki_info.json")
PY

if [ ! -f /tmp/_fix_tsuki_info.json ]; then
  echo "未找到记录，退出。"
  exit 1
fi

echo
echo "===== 2. 删除错误硬链接 ====="
python3 - <<'PY'
import json, os, shutil
with open("/tmp/_fix_tsuki_info.json") as f:
    info = json.load(f)

dest_full = os.path.join(info["dest_path"], info["dest_filename"])
print(f"  目标文件: {dest_full}")

if os.path.exists(dest_full):
    os.remove(dest_full)
    print(f"  已删除文件: {dest_full}")
else:
    print(f"  文件不存在（可能已删除）: {dest_full}")

# 检查父目录是否为空，如果为空则删除
parent = info["dest_path"]
while parent and parent != info.get("dest", ""):
    if os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
        print(f"  已删除空目录: {parent}")
        parent = os.path.dirname(parent)
    else:
        break

# 也检查 DEST 目录下的 show 根目录（如 ゆがんだ月 (1959)）
dest_root = info["dest"]
if dest_root and os.path.isdir(dest_root):
    # 找到 ゆがんだ月 相关的目录
    for entry in os.listdir(dest_root):
        if "ゆがんだ月" in entry:
            show_dir = os.path.join(dest_root, entry)
            if os.path.isdir(show_dir):
                # 递归检查是否为空
                empty = True
                for root, dirs, files in os.walk(show_dir):
                    if files:
                        empty = False
                        break
                if empty:
                    shutil.rmtree(show_dir)
                    print(f"  已删除空剧集目录: {show_dir}")
                else:
                    print(f"  剧集目录非空，保留: {show_dir}")
PY

echo
echo "===== 3. 确认源文件存在 ====="
python3 - <<'PY'
import json, os
with open("/tmp/_fix_tsuki_info.json") as f:
    info = json.load(f)
src = os.path.join(info["source_path"], info["source_filename"])
if os.path.exists(src):
    size_mb = os.path.getsize(src) / 1024 / 1024
    print(f"  源文件存在: {src}  ({size_mb:.0f} MB)")
else:
    print(f"  源文件不存在: {src}")
    print("  无法重新转移，请手动处理。")
PY

echo
echo "===== 4. 重新触发转移 ====="
python3 - <<'PY'
import json, os, urllib.request, urllib.parse, http.cookiejar

with open("/tmp/_fix_tsuki_info.json") as f:
    info = json.load(f)

url = "http://127.0.0.1:3000"

# 读取登录凭据
try:
    import yaml
    with open("/volume2/docker/nastool/config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    username = cfg.get("app", {}).get("login_user", "admin")
    password = cfg.get("app", {}).get("login_password", "password")
except:
    username, password = "admin", "password"

# 使用 cookie 登录
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# Step 1: 登录
login_data = urllib.parse.urlencode({
    "username": username,
    "password": str(password),
    "remember": "on"
}).encode()
req_login = urllib.request.Request(f"{url}/", data=login_data, method="POST")
try:
    opener.open(req_login, timeout=10)
    print("  登录成功")
except Exception as e:
    print(f"  登录失败: {e}")

# Step 2: 调用 rename API
src_path = os.path.join(info["source_path"], info["source_filename"])
payload = json.dumps({
    "cmd": "rename",
    "data": {
        "logid": info["logid"],
        "syncmod": "link"
    }
}).encode("utf-8")

req_rename = urllib.request.Request(
    f"{url}/do",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    with opener.open(req_rename, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        print(f"  API 返回: {result}")
        code = result.get("code", result.get("retcode", -1))
        if code == 0:
            print("  转移成功！")
        else:
            msg = result.get("msg", result.get("retmsg", ""))
            print(f"  转移结果: {msg}")
            print("  请在 NASTool Web UI 手动处理。")
except Exception as e:
    print(f"  API 调用失败: {e}")
    print("  请在 NASTool Web UI 中手动重新识别。")
    print(f"  路径: 媒体整理 -> 手动识别 -> 找到日志ID {info['logid']} 点修复")
PY

echo
echo "===== 5. 清理临时文件 ====="
rm -f /tmp/_fix_tsuki_info.json

echo
echo "__DONE__"
