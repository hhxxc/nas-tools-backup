# 归档清单 2026-10-10

由代码体检（报告：.workbuddy/reports/code-audit-2026-10-10.md）产生的归档，全部为移动而非删除，可随时移回根目录。

## 为什么归档

### shell（66 个）
- `_cc0~_cc21`、`_ccpre31/_ccres31/_cc_webchk` 等：CookieCloud 部署时间线脚本，已被根目录 `_cc.sh`（probe/deploy/status/uuid 子命令）统一替代。`_cc19.sh`（README）仍留根目录。
- `_fb4~_fb8(+_g)`、`_qb9~_qb11(+_g)`、`_mt1~_mt4(+_g/_h)`、`_cc_launch` 系列：内容只差一个文件名数字的 launcher 模板，已被 `_run.sh <name>` / `_get.sh <name>` 替代。
- `_fb0~_fb3` 系列中间版（保留 `_fb_run.sh`）。

### python（32 个）
- SSH 工具链 `_rrun*/_put*/_cd31/_run_file/_run_patched/_run_plain/_fixrun31/_mh/_ssh_restart`：
  被根目录公共库 `_ssh.py` 替代。**注意：这些文件含明文 SSH 密码，归档后仍未脱敏，仅作历史留存。**
- `_haidan*` 中间版（保留 `_haidan_probe.py`、`_haidan_verify.py`）
- TMDB 排查中间版 `_abtest/_t100*/_verify/_diag_fail/_final_diag/_final_verify`（保留 `_verify3.py`、`_applyverify.py`）

## 补充归档（2026-10-10 第二批）
- `mt-timeline/` 子目录：m-team 排障时间线 9 个步骤脚本（_mtfinal/_mtprobe/_mtproxy/_mtpx/_mtrule/_mtscope/_mtv2/_mtv3/_mtverify）+ jellyfin 排障 _jf3/_jf4/_jf5（已脱敏）。均为一次性诊断，问题已解决；保留 `_mt_run.sh`、`_jflib31.sh`、`_jflog.sh`。
- `_t1del31.sh`：含硬编码 `rm -rf` 的一次性清理脚本，为防误执行归档隔离。
- py 时间线第二批：订阅搜索排障 _fb0~_fb7/_fb_test（留 _fb8）、The 100 碰撞 _mt1~_mt3/_mt_body/_mt_search/_mt_titles/_mtfinal（留 _mt4/_mt_diag）、CN 搜索 _why/_two（留 _why2/_v1）、验证码链 _cap/_cap2/_tok/_verify2（留 _pin/_verify3/_applyverify）

## 第三批：lib/dirs/jf 时间线（lib-dirs-timeline/ 子目录）
- sh 演进链非终版：_cat2/_cat3（留 _catall+_catverify）、_cleanup~3（留 _cleanup4+_cleanup_fb）、_dark（留 _dark2）、_dirs~_dirs6（留 _dirs7）、_lg/_lg2（留 _lg3）、_libenum~3（留 _libenum4）、_libscan~3（留 _libscan4）、_libstruct/_libstruct2（留 _libstruct3）、_rw~_rw3（留 _rw4）、_who（留 _who2）、_cfg（留 _cfg31）、_patchtest（留 _patchtest2）、_sshdprep（留 _sshdprep2）
- py：_jf2/_jf6~_jf10（2026-09-28 jellyfin 剧集 ID 解析时间线，留 _jf11）、_tvchk（TV 类型链，留 _tvtype/_epchk）
- 核实后保留：_mickey2/_chk2/_r2 与前代差异过大非演进；_flatten/_flatten_inv 互逆操作均保留
