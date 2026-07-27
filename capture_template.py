"""一键截取"立即签到"按钮模板（无需手工裁剪）。

运行：python capture_template.py
操作：屏幕变暗后，用鼠标拖拽框选 WPS 里的"立即签到"按钮，松开即保存到
      assets/sign_button.png。
"""
from __future__ import annotations

from pathlib import Path

import tkinter as tk
from PIL import ImageGrab

OUT = Path(__file__).parent / "assets" / "sign_button.png"


class Capture:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.attributes("-fullscreen", True)
        root.attributes("-alpha", 0.3)
        root.configure(bg="black")
        self.canvas = tk.Canvas(root, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)
        self.start = None
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_down)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_up)
        hint = tk.Label(
            root, text="拖拽框选「立即签到」按钮，松开鼠标即可保存",
            fg="white", bg="black", font=("Microsoft YaHei", 14),
        )
        hint.place(x=20, y=20)

    def on_down(self, e):
        self.start = (e.x_root, e.y_root)
        self.rect = self.canvas.create_rectangle(
            e.x_root, e.y_root, e.x_root, e.y_root, outline="red", width=2
        )

    def on_drag(self, e):
        self.canvas.coords(self.rect, self.start[0], self.start[1], e.x_root, e.y_root)

    def on_up(self, e):
        x1, y1 = self.start
        x2, y2 = e.x_root, e.y_root
        self.root.destroy()
        bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        img = ImageGrab.grab(bbox)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        img.save(OUT)
        print(f"已保存按钮模板：{OUT}")


if __name__ == "__main__":
    r = tk.Tk()
    Capture(r)
    r.mainloop()
