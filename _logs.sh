#!/bin/bash
D=/usr/local/bin/docker

echo "===== A. did each subscription ever reach the download step? ====="
for n in 特工 铁雨 共同警备区 杀死比尔2 米奇妙妙屋 装备我最强; do
  cnt=$($D logs nastool 2>&1 | grep -c "$n")
  dl=$($D logs nastool 2>&1 | grep "$n" | grep -cE "添加任务|下载")
  fail=$($D logs nastool 2>&1 | grep "$n" | grep -c "未下载到资源")
  echo "  $n: total=$cnt  download_attempts=$dl  not_downloaded=$fail"
done

echo
echo "===== B. every 未下载到资源 line ====="
$D logs nastool 2>&1 | grep -B3 "未下载到资源" | tail -40

echo
echo "===== C. every 登录出错 line ====="
$D logs nastool 2>&1 | grep "登录出错" | tail -10

echo
echo "===== D. has subscribe_search_all ever run? ====="
$D logs nastool 2>&1 | grep -E "共有 .* 个电影订阅需要搜索|共有 .* 个电视剧订阅需要检索" | tail -10
echo "  --- count ---"
$D logs nastool 2>&1 | grep -c "个电影订阅需要搜索"

echo "__DONE__"
