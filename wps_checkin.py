"""WPS 桌面客户端积分签到自动化。

完整流程：
  1. 若 WPS 没运行 -> 自动启动；若已运行 -> 复用窗口；
  2. 激活窗口；
  3. 点击右上角"打开右侧面板"图标；
  4. 等待面板滑出；
  5. 在右侧面板中匹配"立即签到"按钮并点击。
"""
from __future__ import annotations

import argparse
import glob
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.3

ASSETS_DIR = Path(__file__).parent / "assets"
OPEN_PANEL_UNPRESSED_PATH = ASSETS_DIR / "open_panel_unpressed.png"  # 右上角面板图标（未按下）
OPEN_PANEL_PRESSED_PATH = ASSETS_DIR / "open_panel_pressed.png"      # 右上角面板图标（已按下）
DETAILS_PANEL_PATH = ASSETS_DIR / "details_panel_opened.png"         # 面板打开后出现的详情内容（用于判断面板是否真正打开）
SIGN_BUTTON_PATH = ASSETS_DIR / "sign_button.png"                    # "立即签到"按钮
REWARD_BUTTON_PATH = ASSETS_DIR / "reward_button.png"                # "查看奖励"按钮
REWARD_AREA_PATH = ASSETS_DIR / "reward_area.png"                    # 供 AI 识别的奖励区域截图
WPS_LOGO_PATH = ASSETS_DIR / "wps_logo.png"                          # 标题栏左上角 WPS Office 图标（点击可回到首页）
PANEL_CONTENT_PATH = ASSETS_DIR / "panel_content.png"                # 面板内"精选推荐"文字（面板真正打开后才出现的二次确认）
CONFIDENCE = 0.78
REWARD_CONFIDENCE = 0.72
DETAILS_PANEL_CONFIDENCE = 0.72                                       # 详情模板匹配阈值（详情内容较长，可适当放低）
WPS_LOGO_CONFIDENCE = 0.65                                            # WPS logo 模板阈值（图标较小，放低些）
PANEL_CONTENT_CONFIDENCE = 0.72                                       # "精选推荐"模板阈值（文字模板）
LAUNCH_TIMEOUT = 30
PANEL_ANIMATION_DELAY = 1.2                         # 右侧面板滑出动画时间
OPEN_PANEL_MAX_RETRIES = 5                          # 点击面板图标后未检测到详情的最大重试次数
WPS_PATH = r""  # 默认留空，自动用 Everything(es.exe) 定位；定位失败时手动填写完整路径

# 签到完成后的收尾动作：
#   "minimize" -> 最小化 WPS（默认，避免误关未保存文档）
#   "close"    -> 关闭 WPS 主窗口（若仍有未保存文档 WPS 会弹确认，不会硬关）
AFTER_SIGNIN = "minimize"


def is_home_window(title: str) -> bool:
    """首页窗口标题形如 'WPS Office' 或 'WPS Office - WPS Office'。"""
    if title == "WPS Office":
        return True
    parts = title.rsplit(" - ", 1)
    return len(parts) == 2 and parts[0].strip() == "WPS Office"


def find_wps_window():
    """查找 WPS 窗口；优先返回首页窗口，否则返回任意 WPS 窗口。"""
    wins = []
    for w in gw.getAllWindows():
        title = w.title
        if not title:
            continue
        if "WPS" in title or "WPS Office" in title:
            wins.append(w)
    if not wins:
        return None
    for w in wins:
        if is_home_window(w.title):
            return w
    return wins[0]


def find_wps_exe() -> str | None:
    if WPS_PATH and os.path.exists(WPS_PATH):
        return WPS_PATH
    # 优先用 Everything(es.exe) 毫秒级定位最新版 wps.exe
    es = r"C:\Program Files\Everything\es.exe"
    if os.path.exists(es):
        try:
            out = subprocess.check_output(
                [es, "wps.exe"], text=True, timeout=15, stderr=subprocess.DEVNULL
            )
            cands = [
                ln.strip()
                for ln in out.splitlines()
                if ln.strip().lower().endswith("wps.exe")
                and "_bk" not in ln
                and "diffbase" not in ln
            ]
            if cands:
                # 路径中 WPS Office\xx.xx 数字越大越新 -> 取版本号最大者
                def ver_key(p):
                    nums = (
                        re.findall(r"\d+", p.split("WPS Office")[-1])
                        if "WPS Office" in p
                        else []
                    )
                    return [int(n) for n in nums] or [0]

                return max(cands, key=ver_key)
        except Exception:
            pass
    # 兜底：常规目录 glob
    bases = [
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
        os.environ.get("LOCALAPPDATA"),
    ]
    for base in bases:
        if not base:
            continue
        hits = glob.glob(os.path.join(base, "**", "wps.exe"), recursive=True)
        if hits:
            return hits[0]
    return None


def launch_wps():
    exe = find_wps_exe()
    if not exe:
        raise FileNotFoundError(
            "找不到 wps.exe。请确认已安装 WPS，或在脚本顶部 WPS_PATH 手动填写路径。"
        )
    print(f"WPS 未运行，正在启动首页：{exe}")
    subprocess.Popen([exe, "/home"])
    for _ in range(LAUNCH_TIMEOUT):
        w = find_wps_window()
        if w:
            return w
        time.sleep(1)
    raise TimeoutError("WPS 启动超时，未检测到窗口。")


def ensure_wps_window():
    w = find_wps_window()
    if w:
        print("检测到 WPS 已在运行，使用现有窗口。")
        return w
    return launch_wps()


def activate_window(win):
    if win.isMinimized:
        win.restore()
    # 用 Windows API 强制置顶，RDP/后台会话比 win.activate() 更稳
    try:
        import ctypes

        hwnd = win._hWnd
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0001
        SWP_NOSIZE = 0x0002
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
        time.sleep(0.2)
        user32.SetWindowPos(
            hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
    except Exception:
        win.activate()
    time.sleep(1.0)


def goto_home(win, timeout: int = 10) -> bool:
    """如果当前不是 WPS 首页，回到首页。

    策略：点击标题栏左上角的 WPS Office 图标（始终出现在每个 WPS 窗口的左上角，
    点击后会弹出菜单/回到首页，无论打开了多少文档都有效）。
    """
    if is_home_window(win.title):
        return True
    print("当前为文档窗口，尝试回到 WPS 首页...")
    win_left, win_top = win.left, win.top

    # 优先用模板匹配找到 WPS 图标（更精确，能自适应不同 DPI）
    cx, cy, score = (None, None, 0.0)
    if WPS_LOGO_PATH.exists():
        # 图标较小，scale=1.0 保留原细节；只在标题栏范围内搜，减少误匹配
        cx, cy, score = find_template(WPS_LOGO_PATH, WPS_LOGO_CONFIDENCE, scale=1.0)

    if cx is None:
        # 模板没匹配上（图标版本不一致或截屏 DPI 异常），退化到窗口左上角的固定坐标
        # 经验值：图标在标题栏最左侧，距窗口左边缘约 20px、距窗口顶部约 12px
        cx, cy = win_left + 30, win_top + 12
        print(f"[回首页] 未匹配到 WPS logo（分数 {score:.2f}），退化到固定坐标 ({cx},{cy})")
    else:
        print(f"[回首页] 已匹配 WPS logo（分数 {score:.2f}），点击 ({cx},{cy})")

    pyautogui.click(cx, cy)
    # 第一次点击通常会弹出"首页/新建/打开"菜单，再点一次相同位置确认进入首页
    time.sleep(0.6)
    pyautogui.click(cx, cy)

    for _ in range(timeout):
        time.sleep(0.5)
        w = find_wps_window()
        if w and is_home_window(w.title):
            return True
    return False


def find_template(template_path: Path, confidence: float, scale: float = 0.5):
    """返回 (中心x, 中心y, 分数) 或 (None, None, 分数)。

    默认先对截图和模板做 0.5 倍缩放再匹配，可显著降低内存占用并提速。
    """
    shot = pyautogui.screenshot()
    shot_cv = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
    tpl = cv2.imread(str(template_path))
    if tpl is None:
        return None, None, 0.0

    if scale != 1.0 and scale > 0.0:
        shot_cv = cv2.resize(shot_cv, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        tpl = cv2.resize(tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    res = cv2.matchTemplate(shot_cv, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= confidence:
        cx = int((max_loc[0] + tpl.shape[1] // 2) / scale)
        cy = int((max_loc[1] + tpl.shape[0] // 2) / scale)
        return cx, cy, max_val
    return None, None, max_val


def click_template(template_path: Path, label: str) -> tuple[bool, float]:
    cx, cy, score = find_template(template_path, CONFIDENCE)
    if cx is not None:
        pyautogui.click(cx, cy)
        print(f"已点击 [{label}]（匹配度 {score:.2f}）")
        return True, score
    print(f"未找到 [{label}]（匹配度 {score:.2f}）")
    return False, score


def details_panel_visible(pressed_score: float = 0.0) -> tuple[bool, float]:
    """检测屏幕中是否出现面板内容（面板打开后才出现的元素）。

    双重模板确认（避免单个模板误匹配）：
      - 主模板 details_panel_opened.png（详情图标）
      - 副模板 panel_content.png（"精选推荐"标题，仅面板内出现）

    判定逻辑（按优先级）：
      1. 两个模板都存在时，都匹配 → 面板肯定打开；
      2. 两个模板都存在，但仅一个达标，且图标按下分 > 0.85 → 高置信度说明面板已开，
         放宽为"仅一个匹配阈值 * 0.8"即可（避免 `panel_content` 因截图偏小匹配不佳）；
      3. 都匹配不上，但图标按下分超高（>= 0.90）→ 视为打开（跳过 N 次无意义重试）；
      4. 只有一个模板存在时退化到单模板匹配（向后兼容旧配置）。

    返回 (是否可见, 有效匹配度)。
    """
    has_details = DETAILS_PANEL_PATH.exists()
    has_content = PANEL_CONTENT_PATH.exists()

    if not has_details and not has_content:
        return False, 0.0

    score_details = 0.0
    score_content = 0.0

    if has_details:
        _, _, score_details = find_template(DETAILS_PANEL_PATH, DETAILS_PANEL_CONFIDENCE, scale=1.0)
    if has_content:
        _, _, score_content = find_template(PANEL_CONTENT_PATH, PANEL_CONTENT_CONFIDENCE, scale=1.0)

    # 两个都存在
    if has_details and has_content:
        details_ok = score_details >= DETAILS_PANEL_CONFIDENCE
        content_ok = score_content >= PANEL_CONTENT_CONFIDENCE

        if details_ok and content_ok:
            return True, min(score_details, score_content)

        # 都没达标，但图标按下分极高 → 跳过重试，视为打开
        if not details_ok and not content_ok and pressed_score >= 0.90:
            return True, max(score_details, score_content)

        # 仅一个达标 + 图标高置信 → 放宽非达标模板的阈值为 0.8x
        relaxed_threshold = DETAILS_PANEL_CONFIDENCE * 0.8
        if pressed_score >= 0.85:
            if (details_ok and score_content >= relaxed_threshold) or \
               (content_ok and score_details >= relaxed_threshold):
                return True, min(score_details, score_content)

        return False, min(score_details, score_content)

    # 只有 details 模板
    if has_details:
        return score_details >= DETAILS_PANEL_CONFIDENCE, score_details
    # 只有 panel_content 模板
    return score_content >= PANEL_CONTENT_CONFIDENCE, score_content


def open_panel() -> bool:
    """打开右侧面板：先按图标状态判定初始，再点击后用「详情+精选推荐」双重模板确认。

    策略：
      1. 同时匹配未按下/已按下两种图标状态；
      2. 若已按下模板高分命中，再检查双重详情模板；若双重可见，认为面板已打开；
      3. 若未按下模板高分命中，则点击；点击后检查双重详情模板是否出现；
      4. 双重详情模板未出现时，连续点击 OPEN_PANEL_MAX_RETRIES 次（每次后等动画）；
      5. 仍找不到则继续往下走（不阻塞签到流程）。

    双重确认可避免「详情模板」单一匹配产生误判（如非最大化窗口下首页元素恰好匹配）。
    """
    unpressed_exists = OPEN_PANEL_UNPRESSED_PATH.exists()
    pressed_exists = OPEN_PANEL_PRESSED_PATH.exists()

    if not unpressed_exists and not pressed_exists:
        print("缺少面板入口模板（open_panel_unpressed.png / open_panel_pressed.png），跳过开面板步骤。")
        return False

    # 同时匹配两种状态，按较高分判定当前状态；图标较小，用原图匹配更准
    cx_up, cy_up, score_up = (
        find_template(OPEN_PANEL_UNPRESSED_PATH, CONFIDENCE, scale=1.0)
        if unpressed_exists
        else (None, None, 0.0)
    )
    cx_pd, cy_pd, score_pd = (
        find_template(OPEN_PANEL_PRESSED_PATH, CONFIDENCE, scale=1.0)
        if pressed_exists
        else (None, None, 0.0)
    )

    # 优先选择当前图标中心；若未按下分数明显更高，用未按下中心
    if cx_up is not None and (cx_pd is None or score_up >= score_pd):
        click_cx, click_cy, click_score = cx_up, cy_up, score_up
        clicked_state = "unpressed"
    elif cx_pd is not None:
        click_cx, click_cy, click_score = cx_pd, cy_pd, score_pd
        clicked_state = "pressed"
    else:
        print(f"未找到 [打开右侧面板] 图标（未按下 {score_up:.2f}，已按下 {score_pd:.2f}）")
        return False

    # 立即先校验一次面板内容：若已存在，说明面板本就开着，不必再点
    visible, det_score = details_panel_visible(pressed_score=score_pd)
    if visible:
        print(f"检测到面板内容模板（双重确认匹配度 {det_score:.2f}），面板已开。")
        return True

    # 未检测到面板内容，尝试点击图标打开面板（最多重试 N 次）
    for attempt in range(1, OPEN_PANEL_MAX_RETRIES + 1):
        pyautogui.click(click_cx, click_cy)
        print(f"[第{attempt}/{OPEN_PANEL_MAX_RETRIES}次] 点击图标（{click_cx},{click_cy}，图标匹配 {click_score:.2f}）…")
        time.sleep(PANEL_ANIMATION_DELAY)

        visible, det_score = details_panel_visible(pressed_score=score_pd)
        if visible:
            print(f"✓ 面板内容模板出现（双重确认匹配度 {det_score:.2f}），面板已成功打开。")
            return True

        print(f"  面板内容模板未出现（双重确认匹配度 {det_score:.2f}）。")

    print(f"⚠️ 连续 {OPEN_PANEL_MAX_RETRIES} 次点击仍未检测到面板内容模板，继续执行后续签到。")
    return True


def region_around(cx: int, cy: int, w: int = 220, h: int = 100):
    """截取以 (cx,cy) 为中心的 w×h 区域，用于点击前后对比。"""
    shot = pyautogui.screenshot()
    x1 = max(0, cx - w // 2)
    y1 = max(0, cy - h // 2)
    x2 = min(shot.width, x1 + w)
    y2 = min(shot.height, y1 + h)
    return np.array(shot.crop((x1, y1, x2, y2)))


def region_diff(before: np.ndarray, after: np.ndarray) -> float:
    """返回两张图平均绝对像素差。"""
    if before.shape != after.shape:
        return float("inf")
    return float(np.mean(np.abs(after.astype(np.float32) - before.astype(np.float32))))


def detect_button_state() -> tuple[str, tuple[int, int] | None, float]:
    """检测右侧面板按钮状态。

    返回 (state, center, score) :
      - state: "sign" | "reward" | "unknown"
      - center: 按钮中心坐标 (cx, cy)，state 为 unknown 时为 None
      - score: 最高匹配度
    """
    # 签到/奖励按钮较小，用原图匹配更准；面板图标较大，可用缩放省内存
    cx_sign, cy_sign, score_sign = find_template(SIGN_BUTTON_PATH, CONFIDENCE, scale=1.0)
    cx_rwd, cy_rwd, score_rwd = find_template(REWARD_BUTTON_PATH, REWARD_CONFIDENCE, scale=1.0)
    if cx_sign is not None and (cx_rwd is None or score_sign >= score_rwd):
        return "sign", (cx_sign, cy_sign), score_sign
    if cx_rwd is not None and (cx_sign is None or score_rwd > score_sign):
        return "reward", (cx_rwd, cy_rwd), score_rwd
    return "unknown", None, max(score_sign, score_rwd)


def capture_reward_area(center: tuple[int, int] | None = None) -> Path:
    """截取右侧面板奖励信息区域并保存，供 AI 识别连签天数与今日奖励。"""
    shot = pyautogui.screenshot()
    sw, sh = shot.size

    # 统一截取屏幕右侧面板区域，确保 AI 能看到完整的签到卡片信息
    panel_w = min(620, sw)
    x1 = sw - panel_w
    y1 = 0
    x2 = sw
    y2 = min(900, sh)

    region = shot.crop((x1, y1, x2, y2))
    region.save(REWARD_AREA_PATH)
    print(f"奖励区域已保存：{REWARD_AREA_PATH}（{region.size[0]}x{region.size[1]}）")
    return REWARD_AREA_PATH


def do_signin(retries: int = 3, save_screenshot: bool = False) -> tuple[str, Path | None]:
    """执行签到流程。

    返回 (status, reward_path):
      - status:
        "signed"        -> 点击后成功变为"查看奖励"
        "already_signed"-> 发现已经是"查看奖励"/找不到立即签到但面板已打开，今日可能已人工签到
        "failed"        -> 未找到按钮或点击后状态未变化
      - reward_path: 奖励区域截图路径（仅 save_screenshot=True 时返回，否则 None）
    """
    # 先确保右侧面板已打开（避免在全屏主界面误匹配其他蓝色按钮）
    if OPEN_PANEL_UNPRESSED_PATH.exists() or OPEN_PANEL_PRESSED_PATH.exists():
        if not open_panel():
            print("⚠️ 未能确认右侧面板状态，将继续尝试检测按钮。")

    panel_opened = True
    for i in range(retries):
        state, center, score = detect_button_state()

        if state == "reward":
            print(f"检测到 [查看奖励]（匹配度 {score:.2f}），今日可能已人工签到。")
            path = capture_reward_area(center) if save_screenshot else None
            return "already_signed", path

        if state == "unknown":
            # 面板已经打开，但仍找不到"立即签到"，大概率今日已签到（界面显示"明日签到"等）
            if panel_opened:
                print("面板已打开但未找到 [立即签到]，可能今日已签到。")
                path = capture_reward_area() if save_screenshot else None
                return "already_signed", path
            if i < retries - 1:
                time.sleep(1.5)
            continue

        # state == "sign"
        cx, cy = center
        before = region_around(cx, cy)
        pyautogui.click(cx, cy)
        print(f"已点击 [立即签到] 中心（{cx},{cy}，匹配度 {score:.2f}）")

        time.sleep(1.5)  # 等待按钮状态变化

        after = region_around(cx, cy)
        diff = region_diff(before, after)
        state_after, center_after, score_after = detect_button_state()
        print(f"点击后区域差异={diff:.1f}，新状态={state_after}（匹配度 {score_after:.2f}）")

        # 成功判定：按钮变成"查看奖励"，或原按钮匹配度明显下降/区域变化较大
        became_reward = state_after == "reward"
        changed = became_reward or (score_after < 0.75 * score) or (diff > 12.0)

        if became_reward:
            print("按钮已变为 [查看奖励]，签到成功。")
            path = capture_reward_area(center_after) if save_screenshot else None
            return "signed", path
        if changed:
            print("按钮状态已变化，视为签到成功。")
            path = capture_reward_area(center) if save_screenshot else None
            return "signed", path

        if i < retries - 1:
            print("按钮未变化，准备重试...")
            time.sleep(1.5)

    return "failed", None


def finish_wps(action: str = AFTER_SIGNIN) -> None:
    """签到完成后的收尾动作：最小化或关闭 WPS 主窗口。"""
    if action not in ("minimize", "close"):
        return
    try:
        import ctypes

        win = find_wps_window()
        if not win:
            return
        hwnd = win._hWnd
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        if action == "minimize":
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
            print("已最小化 WPS 窗口。")
        else:
            user32.ShowWindow(hwnd, 0)  # SW_HIDE 立即隐藏，避免动画拖影
            time.sleep(0.3)
            # 发送 WM_CLOSE 关闭主窗口（未保存文档会触发 WPS 确认框，不会硬关）
            WM_CLOSE = 0x0010
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
            print("已发送关闭 WPS 窗口指令。")
    except Exception as e:
        print(f"收尾动作执行失败：{e}")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="WPS 桌面客户端积分签到自动化")
    parser.add_argument(
        "--max-delay",
        type=int,
        default=0,
        metavar="SECONDS",
        help="启动后随机等待 0~N 秒再开始签到，用于绕过时间规律检测（默认 0=不等待）",
    )
    parser.add_argument(
        "--with-screenshot",
        action="store_true",
        default=False,
        help="保存奖励区域截图供 AI 识别（默认不保存，省 token 模式）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # 随机延迟：在真正操作前 sleep 一个随机时长，避免每天签到时间完全一致
    delay_seconds = 0
    if args.max_delay > 0:
        delay_seconds = random.randint(0, args.max_delay)
        print(f"[防检测] 随机延迟 {delay_seconds}s（最大 {args.max_delay}s）……")
        time.sleep(delay_seconds)

    if not SIGN_BUTTON_PATH.exists():
        print(f"错误：缺少签到按钮模板 {SIGN_BUTTON_PATH}")
        print("请运行 capture_template.py 截取，或从截图复制到 assets/sign_button.png。")
        return 1
    if not REWARD_BUTTON_PATH.exists():
        print(f"警告：缺少查看奖励模板 {REWARD_BUTTON_PATH}，将无法判断今日是否已签到。")

    win = ensure_wps_window()
    activate_window(win)
    print(f"WPS 窗口就绪：{win.title}")

    if not goto_home(win):
        print("⚠️ 未能自动回到 WPS 首页，将尝试继续签到。")

    status, reward_path = do_signin(save_screenshot=args.with_screenshot)

    delay_info = f"（今日随机延迟 {delay_seconds}s）" if delay_seconds > 0 else ""

    if status == "signed":
        print(f"\n✅ 签到成功。{delay_info}")
        if reward_path:
            print(f"奖励区域截图：{reward_path}")
            print("请 AI 识别该截图中的：已连签天数、今日奖励（积分/会员等）。")
        finish_wps()
        return 0

    if status == "already_signed":
        print(f"\n⚠️ 今日可能已人工签到，本次未执行点击。{delay_info}")
        if reward_path:
            print(f"奖励区域截图：{reward_path}")
            print("请 AI 识别该截图中的：已连签天数、今日奖励（积分/会员等）。")
        finish_wps()
        return 0

    print(f"\n❌ 签到失败。{delay_info}")
    print("可能原因：WPS 界面更新、窗口被遮挡、DPI 缩放变化，或模板图与当前显示不一致。")
    print("请重新截取以下模板再试：")
    print("  - assets/sign_button.png（立即签到按钮）")
    print("  - assets/reward_button.png（查看奖励按钮）")
    print("  - assets/open_panel_unpressed.png（右上角面板图标未按下状态）")
    print("  - assets/open_panel_pressed.png（右上角面板图标已按下状态）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
