/**
 * 第三方插件市场页面脚本
 */

// 全局远程插件缓存
let RemotePlugins = {};
// 风险确认状态
let RemoteRiskConfirmed = false;
// 当前待安装插件
let PendingInstallId = null;

// 加载远程插件清单
function load_remote_plugins(refresh = false) {
  ajax_post(refresh ? "refresh_remote_plugins" : "get_remote_plugins", {}, function (ret) {
    if (ret.code !== 0) {
      show_fail_modal(ret.msg || "获取远程插件失败");
      return;
    }
    RemotePlugins = ret.plugins || {};
    RemoteRiskConfirmed = ret.risk_confirmed;
    render_market_sources(ret.sources || []);
    render_remote_plugins();
  });
}

// 强刷清单
function refresh_remote_plugins() {
  show_wait_modal();
  ajax_post("refresh_remote_plugins", {}, function (ret) {
    hide_wait_modal();
    if (ret.code === 0) {
      load_remote_plugins(false);
      show_success_modal(ret.msg || "刷新成功");
    } else {
      show_fail_modal(ret.msg || "刷新失败");
    }
  });
}

// 渲染市场源配置
function render_market_sources(sources) {
  let lines = [];
  for (let source of sources) {
    lines.push(`${source.name || ''}|${source.repo || ''}|${source.branch || 'main'}`);
  }
  $("#remote_market_sources").val(lines.join('\n'));
}

// 保存市场源
function save_remote_market_sources() {
  let text = $("#remote_market_sources").val() || "";
  let sources = [];
  for (let line of text.split('\n')) {
    if (!line || !line.includes("|")) {
      continue;
    }
    let parts = line.split("|");
    let name = (parts[0] || "").trim();
    let repo = (parts[1] || "").trim();
    let branch = (parts[2] || "").trim() || "main";
    if (!repo) {
      continue;
    }
    sources.push({name: name, repo: repo, branch: branch});
  }
  ajax_post("save_remote_market_sources", {sources: sources}, function (ret) {
    if (ret.code === 0) {
      show_success_modal("市场源保存成功", function () {
        load_remote_plugins(false);
      });
    } else {
      show_fail_modal(ret.msg || "保存失败");
    }
  });
}

// 渲染远程插件列表
function render_remote_plugins() {
  let content = $("#remote_plugins_content").empty();
  let items = Object.entries(RemotePlugins);
  // 已安装的排前面
  items.sort((a, b) => (b[1].installed ? 1 : 0) - (a[1].installed ? 1 : 0));
  if (items.length === 0) {
    content.append(`<div class="text-muted text-center p-4">暂无远程插件，请检查市场源配置后刷新清单。</div>`);
    return;
  }
  for (let [pid, plugin] of items) {
    let icon_html = plugin.icon
      ? (plugin.icon.startsWith('http')
        ? `style="background-image: url('${plugin.icon}')"`
        : `style="background-image: url('../static/img/plugins/${plugin.icon}')"`)
      : '';
    let badge_html = '';
    if (plugin.installed) {
      badge_html = plugin.has_new
        ? `<span class="badge bg-orange position-absolute" style="top: 10px; left: 10px;">可更新</span>`
        : `<span class="badge bg-green position-absolute" style="top: 10px; left: 10px;">已安装</span>`;
    }
    let version_html = plugin.installed && plugin.local_version && plugin.local_version !== plugin.version
      ? `v${plugin.local_version} → v${plugin.version}`
      : `v${plugin.version}`;
    // 操作按钮
    let btn_html = '';
    if (plugin.installed && plugin.has_new) {
      btn_html = `
        <a href="javascript:update_remote_plugin('${pid}', '${plugin.name}')" class="card-btn">
          更新
        </a>
        <a href="javascript:uninstall_remote_plugin('${pid}', '${plugin.name}')" class="card-btn text-danger">
          卸载
        </a>`;
    } else if (plugin.installed) {
      btn_html = `
        <a href="javascript:uninstall_remote_plugin('${pid}', '${plugin.name}')" class="card-btn text-danger">
          卸载
        </a>`;
    } else {
      btn_html = `
        <a href="javascript:install_remote_plugin('${pid}', '${plugin.name}')" class="card-btn">
          安装
        </a>`;
    }
    let card_html = `
      <div class="card card-link-pop card-borderless p-0 shadow-sm rounded-3 overflow-hidden">
        <div class="card-cover card-cover-blurred text-center bg-purple-lt">
          <span class="avatar avatar-xl avatar-thumb avatar-rounded" ${icon_html}>
            ${plugin.icon ? '' : (plugin.name || pid).substring(0, 1)}
          </span>
          ${badge_html}
        </div>
        <div class="card-body text-start">
          <div class="card-title mb-1">${plugin.name || pid}</div>
          <div class="text-muted"><strong>描述：</strong>${plugin.description || ''}</div>
          <div class="text-muted mt-1"><strong>作者：</strong>${plugin.author || ''}</div>
          <div class="text-muted mt-1"><strong>版本：</strong>${version_html}</div>
          <div class="text-muted mt-1"><strong>来源：</strong>${plugin.source_name || ''}</div>
          ${plugin.installed && plugin.installed_time
            ? `<div class="text-muted mt-1"><strong>安装时间：</strong>${plugin.installed_time}</div>` : ''}
        </div>
        <div class="d-flex">
          ${btn_html}
        </div>
      </div>`;
    content.append(card_html);
  }
}

// 安装远程插件（含风险确认）
function install_remote_plugin(id, name) {
  if (RemoteRiskConfirmed) {
    do_install_remote_plugin(id);
    return;
  }
  // 首次安装弹出风险确认
  PendingInstallId = id;
  $("#modal-remote-risk").modal('show');
}

// 风险确认弹窗按钮
$(document).ready(function () {
  $("#remote_risk_btn").unbind('click').click(function () {
    $("#modal-remote-risk").modal('hide');
    // 记录风险确认
    ajax_post("confirm_remote_risk", {}, function (ret) {
      RemoteRiskConfirmed = true;
      if (PendingInstallId) {
        do_install_remote_plugin(PendingInstallId);
        PendingInstallId = null;
      }
    });
  });
});

// 执行安装
function do_install_remote_plugin(id) {
  show_wait_modal();
  ajax_post("install_remote_plugin", {id: id}, function (ret) {
    hide_wait_modal();
    if (ret.code === 0) {
      show_success_modal(ret.msg || "插件安装成功！", function () {
        load_remote_plugins(false);
      });
    } else {
      show_fail_modal(ret.msg || "插件安装失败");
    }
  });
}

// 更新远程插件
function update_remote_plugin(id, name) {
  show_wait_modal();
  ajax_post("update_remote_plugin", {id: id}, function (ret) {
    hide_wait_modal();
    if (ret.code === 0) {
      show_success_modal(ret.msg || "插件更新成功！", function () {
        load_remote_plugins(false);
      });
    } else {
      show_fail_modal(ret.msg || "插件更新失败");
    }
  });
}

// 卸载远程插件
function uninstall_remote_plugin(id, name) {
  show_confirm_modal(`确认卸载插件 ${name} ？`, function () {
    ajax_post("uninstall_remote_plugin", {id: id}, function (ret) {
      if (ret.code === 0) {
        show_success_modal(ret.msg || "插件已卸载！", function () {
          load_remote_plugins(false);
        });
      } else {
        show_fail_modal(ret.msg || "插件卸载失败");
      }
    });
  });
}
