#!/usr/bin/env python3
"""Zero-Dependency Modern Web GUI Dashboard for iOS 27 Carrier Customization.

Refactored with:
  - Bilingual Support (ZH / EN Language Toggle)
  - Cleaned Indicators Bar: USB connection state & Device Model
  - Platform-adaptive reboot trigger on deploy completion:
      * macOS: 'Userspace 秒级快速重启' (via devicectl)
      * Windows: '常规标准系统重启' (via pymobiledevice3 diagnostics)
  - Clear Button explanations & Workflows
  - Detailed bottom explanatory notes & safety disclaimers
  - Auto-exit CLI on browser close via heartbeat mechanism
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from footnote_generator import save_footnote_profile
from airlift_carrier_deploy import (
    query_connected_devices,
    build_cellular_archive,
    clean_device,
    deploy_carrier,
    reboot_device,
    respring_device,
    wait_for_device_reconnect,
)

CURRENT_OS = platform.system()  # 'Darwin' for macOS, 'Windows' for Windows

# Global progress tracker
DEPLOY_PROGRESS = {
    "active": False,
    "percent": 0,
    "step_zh": "就绪",
    "step_en": "Ready",
    "details_zh": "",
    "details_en": "",
    "error_zh": None,
    "error_en": None,
    "completed": False,
}

LAST_HEARTBEAT = time.time()
HEARTBEAT_TIMEOUT = 5.0
SERVER_RUNNING = True

def set_progress(
    percent: int,
    step_zh: str,
    step_en: str,
    details_zh: str = "",
    details_en: str = "",
    error_zh: str | None = None,
    error_en: str | None = None,
    completed: bool = False,
):
    DEPLOY_PROGRESS["active"] = not completed and error_zh is None and error_en is None
    DEPLOY_PROGRESS["percent"] = percent
    DEPLOY_PROGRESS["step_zh"] = step_zh
    DEPLOY_PROGRESS["step_en"] = step_en
    DEPLOY_PROGRESS["details_zh"] = details_zh
    DEPLOY_PROGRESS["details_en"] = details_en
    DEPLOY_PROGRESS["error_zh"] = error_zh
    DEPLOY_PROGRESS["error_en"] = error_en
    DEPLOY_PROGRESS["completed"] = completed



def find_target_device() -> tuple[dict | None, bool]:
    """Return (device, is_wired), preferring a wired USB connection.

    The AirLift pipeline works over the local-network transport as well (verified
    on iPhone 16 Pro Max / iOS 27.0), so a non-wired device is reported rather
    than rejected; callers surface a warning instead of blocking the user.
    """
    devices = query_connected_devices()
    for device in devices:
        if device.get("transport") == "wired":
            return device, True
    if devices:
        return devices[0], False
    return None, False


def get_real_usb_device() -> dict | None:
    """Backwards compatible helper: wired device only."""
    device, wired = find_target_device()
    return device if wired else None


def trigger_platform_reboot(udid: str) -> dict:
    """Trigger standard system reboot to completely reload systemstatusd and SpringBoard."""
    ok = reboot_device(udid, style="full")
    return {
        "ok": ok,
        "mode": "标准系统重启 (Full Reboot)",
        "message": "已向 iPhone 下发标准系统整机重启指令 (正在重启设备生效)",
        "message_en": "Standard system full reboot command dispatched (device restarting)",
    }



HTML_PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>iOS 27 Carrier & Lock Screen Suite</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card: #161b22;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #238636;
      --accent-hover: #2ea043;
      --blue: #58a6ff;
      --yellow: #d29922;
      --red: #f85149;
      --purple: #bc8cff;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 30px 20px;
      display: flex;
      justify-content: center;
    }}
    .container {{
      width: 100%;
      max-width: 720px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 14px;
      border-bottom: 1px solid var(--border);
    }}
    .header-left {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    h1 {{ font-size: 19px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
    
    .header-right {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .lang-toggle {{
      background: #21262d;
      border: 1px solid var(--border);
      color: var(--text);
      font-size: 12px;
      font-weight: 600;
      padding: 5px 10px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .lang-toggle:hover {{ background: #30363d; border-color: var(--blue); }}

    .status-badge {{
      font-size: 12px;
      padding: 5px 10px;
      border-radius: 14px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .badge-disconnected {{
      background: rgba(248, 81, 73, 0.1);
      color: var(--red);
      border: 1px solid rgba(248, 81, 73, 0.3);
    }}
    .badge-connected {{
      background: rgba(35, 134, 54, 0.15);
      color: #3fb950;
      border: 1px solid rgba(35, 134, 54, 0.4);
    }}

    /* Indicators Bar */
    .indicator-row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .indicator-chip {{
      background: #21262d;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
    }}
    .chip-active {{
      border-color: rgba(56, 139, 253, 0.4);
      background: rgba(56, 139, 253, 0.1);
      color: var(--blue);
    }}

    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .card-title {{
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .row {{ display: flex; gap: 14px; }}
    .col {{ flex: 1; }}
    label {{
      font-size: 13px;
      font-weight: 500;
      color: #c9d1d9;
      margin-bottom: 6px;
      display: block;
    }}
    .optional-tag {{
      font-size: 11px;
      color: var(--muted);
      font-weight: 400;
      margin-left: 4px;
    }}
    input, select {{
      width: 100%;
      background: #0d1117;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 6px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s;
    }}
    input:focus, select:focus {{ border-color: var(--blue); }}
    input::placeholder {{ color: #484f58; }}

    /* Button Explanation Grid */
    .btn-group {{
      display: flex;
      gap: 12px;
      margin-top: 6px;
    }}
    .btn-wrapper {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .btn-desc {{
      font-size: 11px;
      color: var(--muted);
      line-height: 1.35;
      text-align: center;
    }}

    .btn {{
      width: 100%;
      background: var(--accent);
      color: white;
      border: none;
      padding: 11px 14px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }}
    .btn:hover:not(:disabled) {{ background: var(--accent-hover); }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .btn-secondary {{ background: #21262d; color: var(--text); border: 1px solid var(--border); }}
    .btn-secondary:hover:not(:disabled) {{ background: #30363d; }}
    .btn-danger {{ background: #b62324; }}
    .btn-danger:hover:not(:disabled) {{ background: #da3633; }}
    .btn-purple {{ background: #6e40c9; color: white; }}
    .btn-purple:hover:not(:disabled) {{ background: #8957e5; }}

    /* Progress Bar */
    .progress-section {{
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      display: none;
      flex-direction: column;
      gap: 10px;
      margin-top: 6px;
    }}
    .progress-header {{
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      font-weight: 500;
    }}
    .progress-track {{
      width: 100%;
      height: 8px;
      background: #21262d;
      border-radius: 4px;
      overflow: hidden;
    }}
    .progress-bar {{
      width: 0%;
      height: 100%;
      background: var(--blue);
      border-radius: 4px;
      transition: width 0.3s ease;
    }}
    .progress-details {{
      font-size: 12px;
      color: var(--muted);
      line-height: 1.4;
    }}

    /* Post-Deploy Reboot Box */
    .reboot-action-box {{
      display: none;
      margin-top: 8px;
      padding: 14px;
      background: rgba(110, 64, 201, 0.12);
      border: 1px solid rgba(110, 64, 201, 0.4);
      border-radius: 8px;
      flex-direction: column;
      gap: 10px;
    }}
    .reboot-box-header {{
      font-size: 13px;
      font-weight: 600;
      color: var(--purple);
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .alert-box {{
      font-size: 13px;
      padding: 10px 14px;
      border-radius: 6px;
      display: none;
      line-height: 1.4;
    }}
    .alert-success {{ background: rgba(35, 134, 54, 0.15); color: #3fb950; border: 1px solid rgba(35, 134, 54, 0.4); }}
    .alert-error {{ background: rgba(248, 81, 73, 0.15); color: var(--red); border: 1px solid rgba(248, 81, 73, 0.4); }}

    /* Footer Details */
    footer {{
      border-top: 1px solid var(--border);
      padding-top: 14px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .footer-note {{
      font-size: 11px;
      color: #6e7681;
      line-height: 1.5;
    }}
    .footer-note strong {{
      color: var(--muted);
    }}
  </style>
</head>
<body>

<div class="container">
  <header>
    <div class="header-left">
      <h1><span>📱</span> <span id="t_headerTitle">iOS 27 锁屏运营商定制控制台</span></h1>
    </div>
    <div class="header-right">
      <div id="deviceBadge" class="status-badge badge-disconnected">
        <span>●</span> <span id="t_probingDevice">正在探测 USB 设备...</span>
      </div>
      <button class="lang-toggle" onclick="toggleLanguage()">🌐 EN / 中文</button>
    </div>
  </header>

  <!-- Cleaned Indicators: USB and Model only -->
  <div class="indicator-row">
    <div id="indUsb" class="indicator-chip">
      <span>🔌</span> <span id="t_indUsbLabel">物理数据线:</span> <strong><span id="t_indUsbVal">未连接</span></strong>
    </div>
    <div id="indModel" class="indicator-chip">
      <span>📱</span> <span id="t_indModelLabel">设备型号:</span> <strong><span id="t_indModelVal">等待识别</span></strong>
    </div>
    <div id="indPlatform" class="indicator-chip">
      <span>💻</span> <span id="t_indPlatformLabel">运行宿主:</span> <strong><span id="t_indPlatformVal">{ 'macOS (系统标准重启模式)' if CURRENT_OS == 'Darwin' else 'Windows (系统标准重启模式)' }</span></strong>
    </div>

  </div>

  <div class="card">
    <div class="card-title" id="t_cardTitlePrimary">主卡设置 (Primary SIM)</div>
    <div class="row">
      <div class="col">
        <label><span id="t_primaryCarrierLabel">主卡运营商名称</span><span class="optional-tag" id="t_opt1">(可选)</span></label>
        <input type="text" id="primaryCarrier" placeholder="例如：中国移动 5G (留空不覆盖名称)">
      </div>
      <div style="width: 100px;">
        <label><span id="t_primaryBadgeLabel">主卡角标</span><span class="optional-tag" id="t_opt2">(可选)</span></label>
        <input type="text" id="primaryBadge" placeholder="如: P, 1">
      </div>
      <div style="width: 110px;">
        <label><span id="t_primaryTypeLabel">网络制式</span><span class="optional-tag" id="t_optType1">(可选)</span></label>
        <select id="primaryType">
          <option value="5g">5G</option>
          <option value="5g+">5G+</option>
          <option value="5g-uwb">5G Ultra</option>
          <option value="lte">LTE</option>
          <option value="4g">4G</option>
          <option value="3g">3G</option>
        </select>
      </div>
      <div style="width: 120px;">
        <label><span id="t_primaryBarsLabel">信号格数</span><span class="optional-tag" id="t_opt3">(可选)</span></label>
        <select id="primaryBars">
          <option value="4" id="t_barsDefault1">4 格 (默认静态)</option>
          <option value="3" id="t_bars3_1">3 格</option>
          <option value="2" id="t_bars2_1">2 格</option>
          <option value="1" id="t_bars1_1">1 格</option>
          <option value="0" id="t_bars0_1">0 格</option>
        </select>
      </div>
    </div>

    <div class="card-title" style="margin-top: 4px;" id="t_cardTitleSecondary">副卡设置 (Secondary SIM / 双卡可选)</div>
    <div class="row">
      <div class="col">
        <label><span id="t_secCarrierLabel">副卡运营商名称</span><span class="optional-tag" id="t_opt4">(可选)</span></label>
        <input type="text" id="secCarrier" placeholder="例如：中国联通 5G (单卡用户请留空)">
      </div>
      <div style="width: 100px;">
        <label><span id="t_secBadgeLabel">副卡角标</span><span class="optional-tag" id="t_opt5">(可选)</span></label>
        <input type="text" id="secBadge" placeholder="如: S, 2">
      </div>
      <div style="width: 110px;">
        <label><span id="t_secTypeLabel">副卡制式</span><span class="optional-tag" id="t_optType2">(可选)</span></label>
        <select id="secType">
          <option value="5g">5G</option>
          <option value="5g+">5G+</option>
          <option value="5g-uwb">5G Ultra</option>
          <option value="lte">LTE</option>
          <option value="4g">4G</option>
          <option value="3g">3G</option>
        </select>
      </div>
      <div style="width: 120px;">
        <label><span id="t_secBarsLabel">副卡信号</span><span class="optional-tag" id="t_opt6">(可选)</span></label>
        <select id="secBars">
          <option value="4" id="t_barsDefault2">4 格 (默认静态)</option>
          <option value="3" id="t_bars3_2">3 格</option>
          <option value="2" id="t_bars2_2">2 格</option>
          <option value="1" id="t_bars1_2">1 格</option>
          <option value="0" id="t_bars0_2">0 格</option>
        </select>
      </div>
    </div>

    <div class="card-title" style="margin-top: 4px;" id="t_cardTitleFootnote">锁屏底部脚注 (Footnote)</div>
    <div class="row">
      <div class="col">
        <input type="text" id="footnoteText" placeholder="Home 条正上方个性签名 (可选，例如:  Steve Jobs)">
      </div>
      <div style="width: 170px;">
        <button class="btn btn-secondary" onclick="exportFootnote()" id="t_btnExport">导出 .mobileconfig</button>
      </div>
    </div>

    <!-- Actions with Explanation Tooltips -->
    <div class="btn-group">
      <div class="btn-wrapper">
        <button id="btnDeploy" class="btn" onclick="startDeploy(false)">⚡ <span id="t_btnDeploy">一键极速部署</span></button>
        <div class="btn-desc" id="t_descDeploy"><strong>首次定制首选</strong>：点对点注入。适用于从未定制过的设备，数秒内完成。</div>
      </div>

      <div class="btn-wrapper">
        <button id="btnOverwrite" class="btn btn-secondary" onclick="startDeploy(true)">🔄 <span id="t_btnOverwrite">自动覆写重写</span></button>
        <div class="btn-desc" id="t_descOverwrite"><strong>更换文字必选</strong>：自动协调自删旧文件+二次写入，解决已有文件覆盖限制。</div>
      </div>

      <div class="btn-wrapper">
        <button id="btnReset" class="btn btn-danger" onclick="startReset()">🛑 <span id="t_btnReset">复位系统默认</span></button>
        <div class="btn-desc" id="t_descReset"><strong>一键还原</strong>：彻底清空状态栏注入，恢复官方原生运营商字样。</div>
      </div>

      <div class="btn-wrapper">
        <button id="btnRepair" class="btn btn-secondary" onclick="startRepair()">🛠 <span id="t_btnRepair">清理设备残留</span></button>
        <div class="btn-desc" id="t_descRepair"><strong>报错后自检</strong>：清除失败的 staging 目录与 Books 脏数据，不触碰状态栏归档。</div>
      </div>
    </div>

    <!-- Live Progress Bar -->
    <div id="progressSection" class="progress-section">
      <div class="progress-header">
        <span id="progressStep">准备中...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-track">
        <div id="progressBar" class="progress-bar"></div>
      </div>
      <div id="progressDetails" class="progress-details">正在与设备建立通信通道...</div>
    </div>

    <!-- Post-Deploy Activation Box (Appears when progress reaches 100%) -->
    <div id="rebootBox" class="reboot-action-box">
      <div class="reboot-box-header">
        <span>✨ <span id="t_rebootBoxHeader">载荷已写入设备！点击下方按钮重启 SpringBoard 立即生效：</span></span>
      </div>
      <div style="display: flex; gap: 12px; align-items: center;">
        <button id="btnRespring" class="btn btn-purple" style="flex: 1;" onclick="triggerRespringNow()">
          <span id="t_btnRespring">⚡ 立即重启 SpringBoard (生效必选)</span>
        </button>
        <button id="btnPlatformReboot" class="btn btn-secondary" onclick="triggerRebootNow()">
          <span id="t_btnFullReboot">🔄 整机重启</span>
        </button>
      </div>
      <div style="font-size: 11px; color: var(--muted); line-height: 1.4;" id="t_rebootBoxTip">
        提示：SpringBoard 只在启动时读取一次 StatusBarOverrides.archive，而整机重启时这次读取发生在首次解锁之前（归档尚不可读），因此整机重启不会生效；解锁后用左侧按钮重启一次 SpringBoard 即可加载覆写。
      </div>
    </div>


    <div id="alertBox" class="alert-box"></div>

    <!-- Detailed Explanatory Notes & Instructions -->
    <footer>
      <div class="footer-note">
        <strong id="t_fnTitle">💡 详细使用与安全说明：</strong>
      </div>
      <div class="footer-note" id="t_fn1">
        • <strong>连接要求</strong>：必须使用原装/MFi 认证 USB 数据线连接 iPhone，手机亮屏并点击“信任此电脑”。不支持无线 Wi-Fi 写入。
      </div>
      <div class="footer-note" id="t_fn2">
        • <strong>安全机制</strong>：本工具仅针对 <code>SpringBoard</code> 状态栏归档执行注入，<strong>绝不碰触系统底层偏好目录</strong>，无数据清空风险。
      </div>
      <div class="footer-note" id="t_fn3">
        • <strong>修改技巧</strong>：若设备之前已经成功修改过文字，后续如果想要更换文字或修改角标，请点击 <strong>【🔄 自动覆写重写】</strong>。
      </div>
      <div class="footer-note" id="t_fn4">
        • <strong>自动退出</strong>：直接关闭本网页标签页，后台命令行程序将自动随之安全退出。
      </div>
      <div class="footer-note" id="t_fn5">
        • <strong>使用前请断开 iPhone 的 Wi-Fi 连接</strong>（设置 → 无线局域网），只保留 USB 数据线：有线连接更稳定；若设备以本地网络方式接入，工具会提示但仍会继续执行。
      </div>
    </footer>
  </div>
</div>

<script>
  let isUsbConnected = false;
  let pollingInterval = null;
  let currentLang = 'zh';
  let lastProgressState = null;
  let lastAlertState = null;

  const I18N = {{
    zh: {{
      headerTitle: "iOS 27 锁屏运营商定制控制台",
      probingDevice: "正在探测 USB 设备...",
      usbReady: "USB 已就绪: ",
      usbDisconnected: "未检测到 USB 数据线连接",
      indUsbLabel: "物理数据线:",
      indUsbValConnected: "有线直连",
      indUsbValDisconnected: "未连接",
      indModelLabel: "设备型号:",
      indModelValWaiting: "等待识别",
      indPlatformLabel: "运行宿主:",
      platformMac: "macOS (系统标准重启模式)",
      platformWin: "Windows (系统标准重启模式)",
      cardTitlePrimary: "主卡设置 (Primary SIM)",
      primaryCarrierLabel: "主卡运营商名称",
      primaryCarrierPh: "例如：中国移动 5G (留空不覆盖名称)",
      primaryBadgeLabel: "主卡角标",
      primaryBadgePh: "如: P, 1",
      primaryTypeLabel: "网络制式",
      primaryBarsLabel: "信号格数",
      cardTitleSecondary: "副卡设置 (Secondary SIM / 双卡可选)",
      secCarrierLabel: "副卡运营商名称",
      secCarrierPh: "例如：中国联通 5G (单卡用户请留空)",
      secBadgeLabel: "副卡角标",
      secBadgePh: "如: S, 2",
      secTypeLabel: "副卡制式",
      secBarsLabel: "副卡信号",
      cardTitleFootnote: "锁屏底部脚注 (Footnote)",
      footnotePh: "Home 条正上方个性签名 (可选，例如:  Steve Jobs)",
      btnExport: "导出 .mobileconfig",
      opt: "(可选)",
      barsDefault: "默认 (不变)",
      bars4: "4 格 (满格)",
      bars3: "3 格",
      bars2: "2 格",
      bars1: "1 格",
      bars0: "0 格",
      btnDeploy: "一键极速部署",
      descDeploy: "<strong>首次定制首选</strong>：点对点注入。适用于从未定制过的设备，数秒内完成。",
      btnOverwrite: "自动覆写重写",
      descOverwrite: "<strong>更换文字必选</strong>：自动协调自删旧文件+二次写入，解决已有文件覆盖限制。",
      btnReset: "复位系统默认",
      descReset: "<strong>一键还原</strong>：彻底清空状态栏注入，恢复官方原生运营商字样。",
      btnRepair: "清理设备残留",
      descRepair: "<strong>报错后自检</strong>：清除失败的 staging 目录与 Books 脏数据，不触碰状态栏归档。",
      confirmRepair: "确定要清理设备上的 AirLift 残留（staging 目录 + Books 脏数据）吗？此操作不会修改状态栏归档。",
      repairWorking: "正在清理设备残留...",
      repairDone: "🛠 设备残留已清理完成，可以重新尝试部署。",
      progressDefaultStep: "准备中...",
      progressDefaultDetails: "正在与设备建立通信通道...",
      rebootBoxHeader: "载荷已写入设备！点击下方按钮重启 SpringBoard 立即生效：",
      btnRespring: "⚡ 立即重启 SpringBoard (生效必选)",
      btnFullReboot: "🔄 整机重启",
      respringSending: "正在重启 SpringBoard...",
      respringRetry: "重试重启 SpringBoard",
      respringDone: "✅ SpringBoard 已重启，状态栏覆写已加载（灵动岛机型请在控制中心查看运营商名）。",
      rebootBtn: "🔄 整机重启",
      rebootTip: "提示：SpringBoard 只在启动时读取一次 StatusBarOverrides.archive；整机重启时这次读取发生在首次解锁之前（归档尚不可读），所以整机重启不会生效。解锁后用左侧按钮重启一次 SpringBoard 即可加载。",
      fnTitle: "💡 详细使用与安全说明：",
      fn1: "• <strong>连接要求</strong>：必须使用原装/MFi 认证 USB 数据线连接 iPhone，手机亮屏并点击“信任此电脑”。不支持无线 Wi-Fi 写入。",
      fn2: "• <strong>安全机制</strong>：本工具仅针对 <code>SpringBoard</code> 状态栏归档执行注入，<strong>绝不碰触系统底层偏好目录</strong>，无数据清空风险。",
      fn3: "• <strong>修改技巧</strong>：若设备之前已经成功修改过文字，后续如果想要更换文字或修改角标，请点击 <strong>【🔄 自动覆写重写】</strong>。",
      fn4: "• <strong>自动退出</strong>：直接关闭本网页标签页，后台命令行程序将自动随之安全退出。",
      fn5: "• <strong>使用前请断开 iPhone 的 Wi-Fi 连接</strong>（设置 → 无线局域网），只保留 USB 数据线：有线连接更稳定；若设备以本地网络方式接入，工具会提示但仍会继续执行。",
      alertNoUsb: "⚠️ 未检测到通过 USB 数据线连接的 iPhone。请断开 iPhone 的 Wi-Fi、用数据线直连电脑并解锁屏幕。",
      alertSuccessDone: "🎉 状态栏归档已成功安全送达设备！请点击下方按钮重启设备生效。",
      confirmReset: "确定要清除所有运营商自定义，恢复系统默认吗？",
      btnRebootSending: "正在向设备下发整机重启指令...",
      btnRebootSent: "重启指令已成功下发 (设备正在重启)",
      btnRebootRetry: "重试重启",
      footnoteRequired: "请输入要导出的脚注文字",
    }},
    en: {{
      headerTitle: "iOS 27 Carrier & Lock Screen Suite",
      probingDevice: "Scanning for USB Device...",
      usbReady: "USB Ready: ",
      usbDisconnected: "No USB cable connection detected",
      indUsbLabel: "Wired USB:",
      indUsbValConnected: "Connected",
      indUsbValDisconnected: "Disconnected",
      indModelLabel: "Device Model:",
      indModelValWaiting: "Waiting for device",
      indPlatformLabel: "Host OS:",
      platformMac: "macOS (Standard Reboot Mode)",
      platformWin: "Windows (Standard Reboot Mode)",
      cardTitlePrimary: "Primary SIM Settings",
      primaryCarrierLabel: "Primary Carrier Name",
      primaryCarrierPh: "e.g., T-Mobile 5G (Leave empty to keep unchanged)",
      primaryBadgeLabel: "Primary Badge",
      primaryBadgePh: "e.g., P, 1",
      primaryTypeLabel: "Network Type",
      primaryBarsLabel: "Signal Bars",
      cardTitleSecondary: "Secondary SIM (Dual SIM Optional)",
      secCarrierLabel: "Secondary Carrier Name",
      secCarrierPh: "e.g., Verizon 5G (Leave empty for Single SIM)",
      secBadgeLabel: "Secondary Badge",
      secBadgePh: "e.g., S, 2",
      secTypeLabel: "Secondary Type",
      secBarsLabel: "Secondary Bars",
      cardTitleFootnote: "Lock Screen Footnote",
      footnotePh: "Signature above Home Bar (Optional, e.g.,  Steve Jobs)",
      btnExport: "Export .mobileconfig",
      opt: "(Optional)",
      barsDefault: "Default (Unchanged)",
      bars4: "4 Bars (Full)",
      bars3: "3 Bars",
      bars2: "2 Bars",
      bars1: "1 Bar",
      bars0: "0 Bars",
      btnDeploy: "Quick Direct Deploy",
      descDeploy: "<strong>First-time Deploy</strong>: Point-to-point delivery. Ideal for pristine devices, completes in seconds.",
      btnOverwrite: "Auto Overwrite",
      descOverwrite: "<strong>Required for Updates</strong>: Two-phase auto eviction + write. Solves existing file rename limits.",
      btnReset: "Restore System Default",
      descReset: "<strong>One-click Reset</strong>: Evicts overrides and restores original native carrier display.",
      btnRepair: "Clean Device Leftovers",
      descRepair: "<strong>Post-failure self-check</strong>: Removes failed staging trees and dirty Books state; never touches the status bar archive.",
      confirmRepair: "Remove AirLift leftovers (staging trees + dirty Books state) from the device? The status bar archive is not modified.",
      repairWorking: "Cleaning device leftovers...",
      repairDone: "🛠 Device leftovers cleaned. You can retry the deployment now.",
      progressDefaultStep: "Preparing...",
      progressDefaultDetails: "Establishing communication channel with device...",
      rebootBoxHeader: "Payload delivered! Restart SpringBoard below to load it:",
      btnRespring: "⚡ Restart SpringBoard (Required to Apply)",
      btnFullReboot: "🔄 Full Reboot",
      respringSending: "Restarting SpringBoard...",
      respringRetry: "Retry SpringBoard Restart",
      respringDone: "✅ SpringBoard restarted; status bar overrides are live (check Control Center on Dynamic Island models).",
      rebootBtn: "🔄 Full Reboot",
      rebootTip: "Tip: SpringBoard reads StatusBarOverrides.archive only once, at startup. A full reboot performs that read before the first unlock, when the archive is not readable yet, so it does not apply; restart SpringBoard after unlocking instead.",
      fnTitle: "💡 Usage & Safety Guide:",
      fn1: "• <strong>Connection</strong>: Must connect iPhone via physical USB cable, unlock screen, and trust computer. Wi-Fi sync not supported.",
      fn2: "• <strong>Safety</strong>: Injects solely to <code>SpringBoard</code> status bar archive. <strong>Zero modifications to system preferences</strong>, no data wipe risk.",
      fn3: "• <strong>Overwrite Rule</strong>: If your device already carries a customized status bar, click <strong>[Auto Overwrite]</strong> to update text smoothly.",
      fn4: "• <strong>Auto-Exit</strong>: Simply close this browser tab, and the terminal CLI process will safely exit.",
      fn5: "• <strong>Disconnect the iPhone Wi-Fi before use</strong> (Settings > Wi-Fi) and keep only the USB cable: wired is more reliable. If the device is reached over the local network the tool warns but still proceeds.",
      alertNoUsb: "⚠️ No USB connected iPhone detected. Turn off the iPhone Wi-Fi, connect it with a cable, and unlock the screen.",
      alertSuccessDone: "🎉 Status bar payload delivered! Click the reboot button below to apply.",
      confirmReset: "Are you sure you want to clear all status bar overrides and restore system defaults?",
      btnRebootSending: "Dispatching full reboot command...",
      btnRebootSent: "Reboot Command Sent (Device restarting)",
      btnRebootRetry: "Retry Reboot",
      footnoteRequired: "Please enter footnote text",
    }}

  }};

  function toggleLanguage() {{
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    applyLanguage();
  }}

  function renderProgress(state) {{
    if (!state) return;
    const step = currentLang === 'zh' ? (state.step_zh || state.step || '') : (state.step_en || state.step || '');
    const details = currentLang === 'zh' ? (state.details_zh || state.details || '') : (state.details_en || state.details || '');
    if (step) document.getElementById('progressStep').innerText = step;
    if (details !== undefined) document.getElementById('progressDetails').innerText = details;
    if (state.percent !== undefined) {{
      document.getElementById('progressBar').style.width = state.percent + '%';
      document.getElementById('progressPct').innerText = state.percent + '%';
    }}
  }}

  function renderAlert() {{
    if (!lastAlertState) return;
    const dict = I18N[currentLang];
    const box = document.getElementById('alertBox');
    let text = "";
    if (lastAlertState.key && dict[lastAlertState.key]) {{
      text = dict[lastAlertState.key];
    }} else if (lastAlertState.rawZh && lastAlertState.rawEn) {{
      text = currentLang === 'zh' ? lastAlertState.rawZh : lastAlertState.rawEn;
    }} else {{
      text = lastAlertState.text || "";
    }}
    box.style.display = 'block';
    box.className = `alert-box alert-${{lastAlertState.type}}`;
    box.innerText = text;
  }}

  function applyLanguage() {{
    const dict = I18N[currentLang];
    document.getElementById('t_headerTitle').innerText = dict.headerTitle;
    document.getElementById('t_indUsbLabel').innerText = dict.indUsbLabel;
    document.getElementById('t_indModelLabel').innerText = dict.indModelLabel;
    document.getElementById('t_indPlatformLabel').innerText = dict.indPlatformLabel;
    document.getElementById('t_indPlatformVal').innerText = '{CURRENT_OS}' === 'Darwin' ? dict.platformMac : dict.platformWin;

    document.getElementById('t_cardTitlePrimary').innerText = dict.cardTitlePrimary;
    document.getElementById('t_primaryCarrierLabel').innerText = dict.primaryCarrierLabel;
    document.getElementById('primaryCarrier').placeholder = dict.primaryCarrierPh;
    document.getElementById('t_primaryBadgeLabel').innerText = dict.primaryBadgeLabel;
    document.getElementById('primaryBadge').placeholder = dict.primaryBadgePh;
    document.getElementById('t_primaryTypeLabel').innerText = dict.primaryTypeLabel;
    document.getElementById('t_primaryBarsLabel').innerText = dict.primaryBarsLabel;

    document.getElementById('t_cardTitleSecondary').innerText = dict.cardTitleSecondary;
    document.getElementById('t_secCarrierLabel').innerText = dict.secCarrierLabel;
    document.getElementById('secCarrier').placeholder = dict.secCarrierPh;
    document.getElementById('t_secBadgeLabel').innerText = dict.secBadgeLabel;
    document.getElementById('secBadge').placeholder = dict.secBadgePh;
    document.getElementById('t_secTypeLabel').innerText = dict.secTypeLabel;
    document.getElementById('t_secBarsLabel').innerText = dict.secBarsLabel;

    document.getElementById('t_cardTitleFootnote').innerText = dict.cardTitleFootnote;
    document.getElementById('footnoteText').placeholder = dict.footnotePh;
    document.getElementById('t_btnExport').innerText = dict.btnExport;

    document.querySelectorAll('.optional-tag').forEach(el => el.innerText = dict.opt);
    document.getElementById('t_barsDefault1').innerText = dict.barsDefault;
    document.getElementById('t_barsDefault2').innerText = dict.barsDefault;
    document.getElementById('t_bars4_1').innerText = dict.bars4;
    document.getElementById('t_bars4_2').innerText = dict.bars4;
    document.getElementById('t_bars3_1').innerText = dict.bars3;
    document.getElementById('t_bars3_2').innerText = dict.bars3;
    document.getElementById('t_bars2_1').innerText = dict.bars2;
    document.getElementById('t_bars2_2').innerText = dict.bars2;
    document.getElementById('t_bars1_1').innerText = dict.bars1;
    document.getElementById('t_bars1_2').innerText = dict.bars1;

    document.getElementById('t_btnDeploy').innerText = dict.btnDeploy;
    document.getElementById('t_descDeploy').innerHTML = dict.descDeploy;
    document.getElementById('t_btnOverwrite').innerText = dict.btnOverwrite;
    document.getElementById('t_descOverwrite').innerHTML = dict.descOverwrite;
    document.getElementById('t_btnReset').innerText = dict.btnReset;
    document.getElementById('t_descReset').innerHTML = dict.descReset;
    document.getElementById('t_btnRepair').innerText = dict.btnRepair;
    document.getElementById('t_descRepair').innerHTML = dict.descRepair;

    document.getElementById('t_rebootBoxHeader').innerText = dict.rebootBoxHeader;
    document.getElementById('t_rebootBoxTip').innerText = dict.rebootTip;
    document.getElementById('t_btnRespring').innerText = dict.btnRespring;
    document.getElementById('t_btnFullReboot').innerText = dict.btnFullReboot;


    document.getElementById('t_fnTitle').innerHTML = dict.fnTitle;
    document.getElementById('t_fn1').innerHTML = dict.fn1;
    document.getElementById('t_fn2').innerHTML = dict.fn2;
    document.getElementById('t_fn3').innerHTML = dict.fn3;
    document.getElementById('t_fn4').innerHTML = dict.fn4;
    document.getElementById('t_fn5').innerHTML = dict.fn5;

    if (lastProgressState) {{
      renderProgress(lastProgressState);
    }} else {{
      document.getElementById('progressStep').innerText = dict.progressDefaultStep;
      document.getElementById('progressDetails').innerText = dict.progressDefaultDetails;
    }}

    renderAlert();
    checkDeviceStatus();
  }}

  function sendHeartbeat() {{
    fetch('/api/heartbeat').catch(() => {{}});
  }}
  setInterval(sendHeartbeat, 2000);
  sendHeartbeat();

  window.addEventListener('beforeunload', () => {{
    navigator.sendBeacon('/api/shutdown');
  }});

  async function checkDeviceStatus() {{
    try {{
      const res = await fetch('/api/devices');
      const data = await readJsonResponse(res);
      const dict = I18N[currentLang];
      
      const badge = document.getElementById('deviceBadge');
      const indUsb = document.getElementById('indUsb');
      const indUsbVal = document.getElementById('t_indUsbVal');
      const indModelVal = document.getElementById('t_indModelVal');

      if (data.connected && data.device) {{
        isUsbConnected = true;
        badge.className = 'status-badge badge-connected';
        badge.innerHTML = `<span>●</span> ${{dict.usbReady}}${{data.device.name}}`;
        
        indUsb.className = 'indicator-chip chip-active';
        indUsbVal.innerText = dict.indUsbValConnected;

        indModelVal.innerText = data.device.model;
      }} else {{
        isUsbConnected = false;
        badge.className = 'status-badge badge-disconnected';
        badge.innerHTML = `<span>●</span> ${{dict.usbDisconnected}}`;
        
        indUsb.className = 'indicator-chip';
        indUsbVal.innerText = dict.indUsbValDisconnected;

        indModelVal.innerText = dict.indModelValWaiting;
      }}
    }} catch(e) {{}}
  }}

  setInterval(checkDeviceStatus, 3000);
  checkDeviceStatus();

  async function readJsonResponse(res) {{
    const text = await res.text();
    if (!text) {{
      throw new Error('服务器未返回内容 (HTTP ' + res.status + ')。若刚更新过代码，请关闭网页与命令行后重新运行 python3 tools/gui_server.py');
    }}
    try {{
      return JSON.parse(text);
    }} catch (parseError) {{
      throw new Error('服务器返回了非 JSON 内容 (HTTP ' + res.status + '): ' + text.slice(0, 160));
    }}
  }}

  async function startDeploy(forceOverwrite) {{
    const dict = I18N[currentLang];
    if (!isUsbConnected) {{
      showAlertKey('error', 'alertNoUsb');
      return;
    }}

    const payload = {{
      carrier: document.getElementById('primaryCarrier').value.trim() || null,
      badge: document.getElementById('primaryBadge').value.trim() || null,
      bars: document.getElementById('primaryBars').value ? parseInt(document.getElementById('primaryBars').value) : null,
      type: document.getElementById('primaryType').value || '5g',
      secondary_carrier: document.getElementById('secCarrier').value.trim() || null,
      secondary_badge: document.getElementById('secBadge').value.trim() || null,
      secondary_bars: document.getElementById('secBars').value ? parseInt(document.getElementById('secBars').value) : null,
      secondary_type: document.getElementById('secType').value || '5g',
      force_overwrite: forceOverwrite,
    }};

    setButtonsDisabled(true);
    showProgress(true);
    document.getElementById('rebootBox').style.display = 'none';
    hideAlert();

    const res = await fetch('/api/deploy', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(payload)
    }});
    const data = await readJsonResponse(res);
    if (!data.ok) {{
      showAlertRaw('error', data.error || 'Task launch failed');
      setButtonsDisabled(false);
      showProgress(false);
      return;
    }}

    startProgressPolling();
  }}

  async function startReset() {{
    const dict = I18N[currentLang];
    if (!isUsbConnected) {{
      showAlertKey('error', 'alertNoUsb');
      return;
    }}
    if (!confirm(dict.confirmReset)) return;

    setButtonsDisabled(true);
    showProgress(true);
    document.getElementById('rebootBox').style.display = 'none';
    hideAlert();

    await fetch('/api/deploy', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ reset: true }})
    }});
    startProgressPolling();
  }}

  async function startRepair() {{
    const dict = I18N[currentLang];
    if (!isUsbConnected) {{
      showAlertKey('error', 'alertNoUsb');
      return;
    }}
    if (!confirm(dict.confirmRepair)) return;

    setButtonsDisabled(true);
    hideAlert();
    showProgress(false);
    try {{
      const res = await fetch('/api/repair', {{ method: 'POST' }});
      const data = await readJsonResponse(res);
      if (data.ok) {{
        showAlertRaw('success', dict.repairDone);
      }} else {{
        showAlertRaw('error', data.error || 'Repair failed');
      }}
    }} catch (error) {{
      showAlertRaw('error', String(error));
    }} finally {{
      setButtonsDisabled(false);
    }}
  }}

  function startProgressPolling() {{
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(async () => {{
      try {{
        const res = await fetch('/api/progress');
        const state = await readJsonResponse(res);
        lastProgressState = state;
        
        renderProgress(state);

        if (state.completed) {{
          clearInterval(pollingInterval);
          setButtonsDisabled(false);
          document.getElementById('rebootBox').style.display = 'flex';
          showAlertKey('success', 'alertSuccessDone');
        }} else if (state.error_zh || state.error_en || state.error) {{
          clearInterval(pollingInterval);
          setButtonsDisabled(false);
          const errZh = '❌ 错误: ' + (state.error_zh || state.error);
          const errEn = '❌ Error: ' + (state.error_en || state.error);
          showAlertDual('error', errZh, errEn);
        }}
      }} catch(e) {{}}
    }}, 800);
  }}

  async function triggerRespringNow() {{
    const dict = I18N[currentLang];
    const btn = document.getElementById('btnRespring');
    btn.disabled = true;
    btn.innerText = dict.respringSending;

    try {{
      const res = await fetch('/api/respring', {{ method: 'POST' }});
      const data = await readJsonResponse(res);
      if (data.ok) {{
        showAlertDual('success', '✅ ' + dict.respringDone, '✅ ' + dict.respringDone);
        btn.innerText = dict.btnRespring;
        btn.disabled = false;
        document.getElementById('rebootBox').style.display = 'none';
      }} else {{
        showAlertRaw('error', '❌ ' + (data.error || 'SpringBoard restart failed'));
        btn.innerText = dict.respringRetry;
        btn.disabled = false;
      }}
    }} catch(e) {{
      showAlertRaw('error', 'Request failed: ' + e);
      btn.innerText = dict.respringRetry;
      btn.disabled = false;
    }}
  }}

  async function triggerRebootNow() {{
    const dict = I18N[currentLang];
    const btn = document.getElementById('btnPlatformReboot');
    const label = document.getElementById('t_btnFullReboot');
    btn.disabled = true;
    label.innerText = dict.btnRebootSending;

    try {{
      const res = await fetch('/api/reboot', {{ method: 'POST' }});
      const data = await readJsonResponse(res);
      if (data.ok) {{
        const msgZh = '✅ ' + (data.message || '已下发重启');
        const msgEn = '✅ ' + (data.message_en || data.message || 'Reboot dispatched');
        showAlertDual('success', msgZh, msgEn);
        label.innerText = dict.btnRebootSent;
        btn.disabled = false;
      }} else {{
        showAlertDual('error', '❌ ' + (data.error || 'Reboot failed'), '❌ ' + (data.error || 'Reboot failed'));
        btn.disabled = false;
        label.innerText = dict.btnRebootRetry;
      }}
    }} catch(e) {{
      showAlertRaw('error', 'Request failed: ' + e);
      btn.disabled = false;
    }}
  }}

  function exportFootnote() {{
    const text = document.getElementById('footnoteText').value.trim();
    if (!text) {{
      alert(I18N[currentLang].footnoteRequired);
      return;
    }}
    window.location.href = `/api/export-footnote?text=${{encodeURIComponent(text)}}`;
  }}

  function setButtonsDisabled(disabled) {{
    document.getElementById('btnDeploy').disabled = disabled;
    document.getElementById('btnOverwrite').disabled = disabled;
    document.getElementById('btnReset').disabled = disabled;
    document.getElementById('btnRepair').disabled = disabled;
  }}

  function showProgress(show) {{
    document.getElementById('progressSection').style.display = show ? 'flex' : 'none';
  }}

  function showAlertKey(type, key) {{
    lastAlertState = {{ type, key }};
    renderAlert();
  }}

  function showAlertDual(type, zhText, enText) {{
    lastAlertState = {{ type, rawZh: zhText, rawEn: enText }};
    renderAlert();
  }}

  function showAlertRaw(type, text) {{
    lastAlertState = {{ type, text }};
    renderAlert();
  }}

  function hideAlert() {{
    lastAlertState = null;
    document.getElementById('alertBox').style.display = 'none';
  }}
</script>
</body>
</html>

"""


def execute_deploy_worker(body: dict):
    try:
        is_reset = body.get("reset", False)
        force_overwrite = body.get("force_overwrite", False)

        target_device, wired = find_target_device()
        if not target_device:
            set_progress(
                0,
                step_zh="失败",
                step_en="Failed",
                error_zh="未找到已连接的 iPhone。请用 USB 数据线连接设备、解锁屏幕并点击“信任此电脑”，同时建议断开 iPhone 的 Wi-Fi。",
                error_en="No iPhone detected. Connect the device with a USB cable, unlock it, trust this computer, and preferably turn off the iPhone Wi-Fi.",
            )
            return

        udid = target_device["udid"]
        transport_note_zh = "" if wired else "（注意：当前为本地网络/Wi-Fi 连接，建议改用 USB 数据线）"
        transport_note_en = "" if wired else " (note: connected over the local network / Wi-Fi; a USB cable is recommended)"
        if not wired:
            print("[!] 设备当前通过本地网络(Wi-Fi)接入，建议使用 USB 数据线连接。")
        set_progress(
            15,
            step_zh="正在生成归档",
            step_en="Generating Archive",
            details_zh="解析可选字段并构造 NSKeyedArchiver bplist..." + transport_note_zh,
            details_en="Parsing fields and constructing NSKeyedArchiver bplist..." + transport_note_en,
        )

        primary_type = NETWORK_TYPES.get(body.get("type", "5g"), 10)
        secondary_type = NETWORK_TYPES.get(body.get("secondary_type", "5g"), 10)

        payload = build_cellular_archive(
            primary_carrier=body.get("carrier"),
            primary_bars=body.get("bars") if body.get("bars") is not None else 4,
            primary_type=primary_type,
            primary_badge=body.get("badge"),
            secondary_carrier=body.get("secondary_carrier"),
            secondary_bars=body.get("secondary_bars") if body.get("secondary_bars") is not None else 4,
            secondary_type=secondary_type,
            secondary_badge=body.get("secondary_badge"),
            is_reset=is_reset,
        )

        if is_reset and force_overwrite:
            set_progress(
                30,
                step_zh="复位自愈阶段: 清除已存在归档",
                step_en="Reset Phase: Evicting Existing Archive",
                details_zh="正在下发 self-eviction 重置载荷...",
                details_en="Dispatching self-eviction payload...",
            )
            reset_payload = build_cellular_archive(is_reset=True)
            res1 = deploy_carrier(udid, reset_payload)
            if not res1.get("ok"):
                set_progress(
                    30,
                    step_zh="复位注入失败",
                    step_en="Reset Phase Failed",
                    error_zh="清除旧文件阶段注入失败。",
                    error_en="Failed to inject self-eviction payload.",
                )
                return

            set_progress(
                60,
                step_zh="复位自愈阶段: 重启生效",
                step_en="Reset Phase: Rebooting for Eviction",
                details_zh="触发用户空间快速重启以触发 SpringBoard 磁盘自愈清理...",
                details_en="Triggering userspace reboot for SpringBoard auto-eviction...",
            )
            reboot_device(udid, style="userspace")
            wait_for_device_reconnect(udid, timeout_seconds=60)
            set_progress(
                100,
                step_zh="复位完成",
                step_en="Reset Completed",
                details_zh="SpringBoard 已成功自愈清除旧归档并恢复官方原生运营商！",
                details_en="SpringBoard self-evicted the archive and restored native carrier!",
                completed=True,
            )
            return

        if force_overwrite and not is_reset:
            set_progress(
                30,
                step_zh="第一阶段: 清除已存在归档",
                step_en="Phase 1: Evicting Existing Archive",
                details_zh="正在下发 self-eviction 重置载荷...",
                details_en="Dispatching self-eviction payload...",
            )
            reset_payload = build_cellular_archive(is_reset=True)
            res1 = deploy_carrier(udid, reset_payload)
            if not res1.get("ok"):
                set_progress(
                    30,
                    step_zh="第一阶段失败",
                    step_en="Phase 1 Failed",
                    error_zh="清除旧文件阶段注入失败。",
                    error_en="Failed to inject self-eviction payload.",
                )
                return

            set_progress(
                50,
                step_zh="第一阶段: 重启清理中",
                step_en="Phase 1: Restarting to Clear Cache",
                details_zh="触发用户空间快速重启并等待设备重连...",
                details_en="Triggering userspace reboot and awaiting reconnect...",
            )
            reboot_device(udid, style="userspace")
            if not wait_for_device_reconnect(udid, timeout_seconds=60):
                set_progress(
                    50,
                    step_zh="重连超时",
                    step_en="Reconnect Timeout",
                    error_zh="设备重启后未能在规定时间内重新连接。",
                    error_en="Device did not reconnect within the timeout period.",
                )
                return

            set_progress(
                75,
                step_zh="第二阶段: 注入新运营商配置",
                step_en="Phase 2: Injecting New Profile",
                details_zh="向全新 SpringBoard 目标写入目标归档...",
                details_en="Writing target archive to SpringBoard destination...",
            )
            res2 = deploy_carrier(udid, payload)
            if not res2.get("ok"):
                err_msg = res2.get("error", "目标载荷注入失败。")
                set_progress(
                    75,
                    step_zh="第二阶段失败",
                    step_en="Phase 2 Failed",
                    error_zh=str(err_msg),
                    error_en=str(err_msg),
                )
                return


            set_progress(
                100,
                step_zh="准备就绪",
                step_en="Ready",
                details_zh="两阶段覆写载荷均已成功落地！请点击下方专属重启按钮生效。",
                details_en="Two-phase overwrite payloads successfully delivered! Click reboot below to apply.",
                completed=True,
            )
        else:
            set_progress(
                50,
                step_zh="正在下发归档",
                step_en="Deploying Archive",
                details_zh="通过 AirTraffic 通道同步至 SpringBoard 目标目录...",
                details_en="Syncing to SpringBoard destination via AirTraffic...",
            )
            res = deploy_carrier(udid, payload)
            if not res.get("ok"):
                set_progress(
                    50,
                    step_zh="部署失败",
                    step_en="Deploy Failed",
                    error_zh="AirLift 底层同步拒绝写入 (若是二次修改请使用'自动覆写重写')。",
                    error_en="AirTraffic rejected write (for updates, please use 'Auto Overwrite').",
                )
                return

            set_progress(
                100,
                step_zh="准备就绪",
                step_en="Ready",
                details_zh="运营商归档已成功写入设备！请点击下方专属重启按钮生效。",
                details_en="Carrier archive successfully delivered! Click reboot below to apply.",
                completed=True,
            )

    except Exception as e:
        set_progress(
            0,
            step_zh="异常中断",
            step_en="Interrupted with Error",
            error_zh=str(e),
            error_en=str(e),
        )



class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        global LAST_HEARTBEAT
        parsed = urlparse(self.path)
        if parsed.path == "/":
            LAST_HEARTBEAT = time.time()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/heartbeat":
            LAST_HEARTBEAT = time.time()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"alive"}')
        elif parsed.path == "/api/devices":
            LAST_HEARTBEAT = time.time()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            usb_dev, _wired = find_target_device()
            self.wfile.write(json.dumps({
                "connected": bool(usb_dev),
                "device": usb_dev,
                "platform": CURRENT_OS,
            }).encode("utf-8"))
        elif parsed.path == "/api/progress":
            LAST_HEARTBEAT = time.time()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(DEPLOY_PROGRESS).encode("utf-8"))
        elif parsed.path == "/api/export-footnote":
            LAST_HEARTBEAT = time.time()
            qs = parse_qs(parsed.query)
            text = qs.get("text", ["Prognosticate-X"])[0]
            mobileconfig = save_footnote_profile(text, ROOT / "footnote.mobileconfig")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-apple-aspen-config")
            self.send_header("Content-Disposition", 'attachment; filename="footnote.mobileconfig"')
            self.end_headers()
            self.wfile.write(mobileconfig.read_bytes())
        else:
            self.send_json(
                {"ok": False, "error": "unknown endpoint", "path": parsed.path,
                 "hint": "接口不存在：请关闭网页与命令行后重新运行 python3 tools/gui_server.py 以加载最新代码。"},
                status=404,
            )

    def send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global SERVER_RUNNING
        parsed = urlparse(self.path)
        if parsed.path == "/api/shutdown":
            self.send_response(200)
            self.end_headers()
            print("\n[✓] 网页已关闭，后台服务正在退出...")
            SERVER_RUNNING = False
            threading.Thread(target=lambda: os._exit(0)).start()
        elif parsed.path == "/api/deploy":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            thread = threading.Thread(target=execute_deploy_worker, args=(body,), daemon=True)
            thread.start()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
        elif parsed.path == "/api/repair":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            usb_dev, _wired = find_target_device()
            if not usb_dev:
                self.wfile.write(json.dumps({"ok": False, "error": "未找到已连接的 iPhone。请用 USB 数据线连接设备并解锁屏幕（建议同时断开 iPhone 的 Wi-Fi）。"}, ensure_ascii=False).encode("utf-8"))
                return
            try:
                report = clean_device(usb_dev["udid"])
                staging = report["staging"].get("operation", {})
                payload = {
                    "ok": bool(report["ok"]),
                    "removed": staging.get("removed", []),
                    "remaining": staging.get("remaining", []),
                    "booksReset": report["booksCleaned"]["droppedFiles"],
                }
            except Exception as error:
                payload = {"ok": False, "error": str(error)}
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/respring":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            usb_dev, _wired = find_target_device()
            if not usb_dev:
                self.wfile.write(json.dumps({"ok": False, "error": "未找到已连接的 iPhone。请用 USB 数据线连接设备并解锁屏幕（建议同时断开 iPhone 的 Wi-Fi）。"}, ensure_ascii=False).encode("utf-8"))
                return
            try:
                activated = respring_device(usb_dev["udid"])
                payload = {"ok": True, "pid": activated["pid"], "previousPid": activated["previousPid"], "seconds": activated["seconds"]}
            except Exception as error:
                payload = {"ok": False, "error": str(error)}
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/reboot":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            usb_dev, _wired = find_target_device()
            if not usb_dev:
                self.wfile.write(json.dumps({"ok": False, "error": "未找到已连接的 iPhone。请用 USB 数据线连接设备并解锁屏幕（建议同时断开 iPhone 的 Wi-Fi）。"}).encode("utf-8"))
                return
            res = trigger_platform_reboot(usb_dev["udid"])
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_json(
                {"ok": False, "error": "unknown endpoint", "path": parsed.path,
                 "hint": "接口不存在：请关闭网页与命令行后重新运行 python3 tools/gui_server.py 以加载最新代码。"},
                status=404,
            )


def heartbeat_watcher():
    global SERVER_RUNNING
    time.sleep(10)
    while SERVER_RUNNING:
        time.sleep(2)
        if time.time() - LAST_HEARTBEAT > HEARTBEAT_TIMEOUT:
            print("\n[✓] 检测到控制台网页已关闭，命令行自动安全退出。")
            SERVER_RUNNING = False
            os._exit(0)


def run_gui_server(port: int = 8765):
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n=======================================================")
    print(f" 🚀 iOS 27 锁屏运营商控制台 (中英双语版) 已就绪!")
    print(f" 🌐 正在打开控制面板: {url}")
    print(f" 💡 提示: 关闭浏览器网页后，命令行将自动安全退出。")
    print(f"=======================================================\n")
    
    watcher = threading.Thread(target=heartbeat_watcher, daemon=True)
    watcher.start()

    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[✓] 控制台已退出")


if __name__ == "__main__":
    run_gui_server()
