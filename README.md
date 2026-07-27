# WPS Auto Check-in / WPS 自动签到

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Version v0.1** — Screen-recognition-based auto check-in for WPS Office desktop client.  
> **重要说明：本版本通过屏幕截图 + 图像模板匹配模拟点击，WPS 窗口需要保持开启。**

---

## 🇬🇧 English

Automate WPS Office desktop client daily points check-in on Windows. The script uses **computer vision (OpenCV template matching)** to locate on-screen buttons and simulate mouse clicks — just like a human would.

**Version v0.1 limitations:**
- ✅ WPS must be **open and visible** on the desktop (minimized is fine, the script will restore it)
- ✅ Works in RDP / remote desktop sessions
- ❌ Does NOT work when the screen is locked or the user is logged out
- ❌ Does NOT use WPS API / plugin — pure screen recognition

### How It Works

1. The script finds or launches WPS, restores its window, and brings it to the foreground
2. Returns to the WPS home page (even if currently in a document/PDF tab)
3. Opens the right-side panel by clicking the top-right icon (detects **unpressed / pressed** states)
4. Looks for one of two buttons in the panel:
   - **立即签到 (Check-in Now)** → clicks it
   - **查看奖励 (View Rewards)** → reports "already checked in today" and skips
5. After successful check-in, captures a screenshot of the reward area for AI/OCR recognition (**only with `--with-screenshot` flag**)
6. Minimizes (default) or closes WPS

### Quick Start

```powershell
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Run once manually to test (default: token-save mode, no screenshot)
python wps_checkin.py

# 3. Set up daily automation (right-click → Run as Administrator)
#    Right-click create_task.ps1 → Run with PowerShell
```

The script supports two optional flags:

```powershell
# Random delay to avoid timing detection
python wps_checkin.py --max-delay 115   # random 0~115s delay before clicking

# Save reward screenshot for AI recognition (costs tokens, off by default)
python wps_checkin.py --with-screenshot
```

### Token-Save Mode (Default)

By default, the script runs in **token-save mode**: it completes the full check-in flow but does NOT save a reward screenshot. The AI determines success/failure purely from the script's stdout text output (e.g. `✅ 签到成功` or `⚠️ 今日可能已人工签到`).

Use `--with-screenshot` only when you need the AI to read reward details (consecutive days, specific rewards). This avoids wasting tokens on image recognition for routine daily check-ins.

默认省 token 模式：脚本完成全部签到流程但不保存截图，AI 直接根据 stdout 文字判断结果。仅在需要 AI 识别连签天数和奖励明细时才加 `--with-screenshot`。

### Anti-Detection

- `--max-delay` adds a random 0~N second sleep before any mouse operation
- Combined with Windows Task Scheduler (trigger at 08:30 + `--max-delay 115`), the actual check-in time falls between 08:30–08:32 randomly
- WPS check-in is a lightweight daily activity — ±57s jitter is sufficient to bypass simple timing checks

### Requirements

- Windows 10/11 + WPS Office desktop client
- Python 3.10+ (with **Add Python to PATH** during installation)
- [Everything](https://www.voidtools.com/) (recommended for fast wps.exe discovery; falls back to common install paths)

### Configuration

Edit the top of `wps_checkin.py`:

```python
CONFIDENCE = 0.78           # Template matching threshold
AFTER_SIGNIN = "minimize"   # "minimize" or "close" after check-in
WPS_PATH = r""              # Leave empty for auto-detect, or fill manually
```

---

## 🇨🇳 中文

Windows 端 WPS Office 桌面客户端积分自动签到。脚本通过 **OpenCV 图像模板匹配（计算机视觉）**识别屏幕上的按钮位置并模拟鼠标点击——就像真人操作一样。

**v0.1 版本说明：**
- ✅ WPS 需**保持打开**（最小化可以，脚本会自动还原窗口）
- ✅ 支持 RDP / 远程桌面会话
- ❌ 屏幕锁定或用户注销时无法运行
- ❌ 不使用 WPS API / 插件——纯屏幕识别

### 工作原理

1. 脚本自动查找或启动 WPS，还原窗口并置顶
2. 自动回到 WPS 首页（即使当前在文档/PDF 标签页）
3. 点击右上角图标打开右侧面板（自动识别未按下/已按下两种图标状态）
4. 在面板中查找两种按钮：
   - **立即签到** → 点击它，并验证按钮变为"查看奖励"
   - **查看奖励** → 提示"今日可能已签到"，跳过点击
5. 签到成功后截图右侧面板奖励区域，供 AI 识别连签天数和今日奖励
6. 默认最小化 WPS（可配置为关闭）

### 快速开始

```powershell
# 1. 安装依赖
python -m pip install -r requirements.txt

# 2. 手动运行测试
python wps_checkin.py

# 3. 设置每日自动签到（右键 → 以管理员身份运行）
#    右键 create_task.ps1 → 使用 PowerShell 运行
```

脚本支持随机启动延迟，防止每天签到时间完全一致：

```powershell
python wps_checkin.py --max-delay 115   # 点击前随机 0~115 秒延迟
```

### 反检测机制

- `--max-delay` 参数在操作鼠标前随机 sleep 0~N 秒
- 配合 Windows 任务计划程序（08:30 触发 + `--max-delay 115`），实际签到时间在 08:30~08:32 之间随机
- WPS 签到是日常轻量活跃功能，±57 秒抖动已足够绕过简单的时间规律检测

### 环境要求

- Windows 10/11 + WPS Office 桌面客户端
- Python 3.10+（安装时勾选 **Add Python to PATH**）
- [Everything](https://www.voidtools.com/) 搜索引擎（推荐，用于毫秒级定位 wps.exe；未安装时自动降级到常规路径查找）

### 配置项

编辑 `wps_checkin.py` 顶部：

```python
CONFIDENCE = 0.78           # 模板匹配阈值，找不到按钮时降低
AFTER_SIGNIN = "minimize"   # 签到后 "minimize" 最小化 / "close" 关闭
WPS_PATH = r""              # 留空自动定位，或手动填写完整路径
```

---

## Assets / 模板图

| File / 文件 | Purpose / 用途 |
|-------------|----------------|
| `open_panel_unpressed.png` | 右上角面板图标（未按下，需要点击） |
| `open_panel_pressed.png` | 右上角面板图标（已按下，面板已打开） |
| `details_panel_opened.png` | 面板打开后内部详情图标（双重确认 #1） |
| `panel_content.png` | "精选推荐"标题文字（双重确认 #2，仅面板内可见，避免单一模板误匹配） |
| `sign_button.png` | 「立即签到」按钮模板 |
| `reward_button.png` | 「查看奖励」按钮模板（用于判断是否已签到） |
| `wps_logo.png` | 标题栏左上角 WPS Office 图标（点击回到首页，无论开了几个文档都有效） |
| `reward_area.png` | 自动生成的奖励面板截图 |

若 WPS 更新界面后匹配失败，用 `capture_template.py` 重新截取：

```powershell
python capture_template.py
```

拖拽框选按钮区域，截图自动保存到 `assets/sign_button.png`。

## Project Structure / 项目结构

```
wps-auto-checkin/
├── wps_checkin.py          # Main script / 主脚本
├── capture_template.py     # Template image capture tool / 模板截图工具
├── create_task.ps1         # Windows Task Scheduler setup / 任务计划程序配置
├── setup.bat               # Dependency installer / 依赖安装脚本
├── run.bat                 # Quick-run launcher / 快速运行脚本
├── requirements.txt        # Python dependencies
├── assets/                 # Image templates / 图像模板
│   ├── open_panel_unpressed.png
│   ├── open_panel_pressed.png
│   ├── details_panel_opened.png
│   ├── panel_content.png       # "精选推荐"（双重确认 #2）
│   ├── wps_logo.png
│   ├── sign_button.png
│   ├── reward_button.png
│   └── reward_area.png         # Auto-generated / 自动生成
├── README.md
└── LICENSE
```

## Safety / 安全说明

- 仅在本机模拟点击用户自己的 WPS 界面，**不上传任何账号信息**
- **执行期间不要动鼠标/键盘**（紧急中止：将鼠标甩到屏幕四角）
- 建议每天只运行 1 次，过于频繁可能触发 WPS 风控

## License

MIT License. See [LICENSE](LICENSE).
