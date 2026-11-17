#!/usr/bin/env python3
"""Generate workspace-architecture.svg (workspace mode) and self-check geometry."""
import sys
from xml.sax.saxutils import escape

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace-architecture.svg")
W, H = 1440, 960
FONT = ("Calibri, Carlito, 'Segoe UI', Arial, 'Noto Sans CJK TC', 'Noto Sans TC', "
        "'PingFang TC', 'Microsoft JhengHei', sans-serif")
BG, FILL, LINE = "#fafafa", "#f0f0f1", "#696c77"
TXT, HEAD, SUB = "#383a42", "#232324", "#50525c"
PURPLE, GREEN, GREEN_T = "#a626a4", "#50a14f", "#3f8f3e"
R = 14

def tw(s, fs, bold=False):
    """Conservative text width."""
    w = 0.0
    for ch in s:
        if ord(ch) > 0x2000:
            w += 1.0
        elif ch == " ":
            w += 0.32
        else:
            w += 0.60 if bold else 0.57
    return w * fs

out = []
texts = []    # (x0,y0,x1,y1,label, owner_rect or None)
leaf = {}     # name -> (x0,y0,x1,y1)
frames = []   # (x0,y0,x1,y1)
paths = []    # (name, color, [pts])
circles = []  # (cx,cy,n,color)

def text(x, y, s, fs, color=TXT, bold=False, anchor="start", owner=None, check=True):
    w = tw(s, fs, bold)
    x0 = x if anchor == "start" else (x - w / 2 if anchor == "middle" else x - w)
    if check:
        texts.append((x0, y - 0.82 * fs, x0 + w, y + 0.22 * fs, s, owner))
    out.append(f'<text x="{x}" y="{y}" font-size="{fs}"'
               + (' font-weight="700"' if bold else '')
               + (f' text-anchor="{anchor}"' if anchor != "start" else '')
               + f' fill="{color}">{escape(s)}</text>')

def box(name, x0, y0, x1, y1, label, fs=18, lines=None):
    leaf[name] = (x0, y0, x1, y1)
    out.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="{FILL}" '
               f'stroke="{LINE}" stroke-width="1.5"/>')
    cx = (x0 + x1) / 2
    if lines:
        n = len(lines)
        cy = (y0 + y1) / 2
        for i, s in enumerate(lines):
            text(cx, round(cy + (i - (n - 1) / 2) * (fs + 5) + fs * 0.34, 1), s, fs,
                 anchor="middle", owner=(x0, y0, x1, y1))
    else:
        text(cx, round((y0 + y1) / 2 + fs * 0.34, 1), label, fs, anchor="middle",
             owner=(x0, y0, x1, y1))

def frame(x0, y0, x1, y1, label, kind, fs=18, lx=None, ly=None):
    frames.append((x0, y0, x1, y1))
    if kind == "ns":
        st = f'fill="none" stroke="{LINE}" stroke-width="2"'
    elif kind == "pod":
        st = f'fill="none" stroke="{LINE}" stroke-width="1.5"'
    elif kind == "container":
        st = f'fill="none" stroke="{LINE}" stroke-width="1.5" stroke-dasharray="5 4"'
    else:  # session
        st = f'fill="#ffffff" stroke="{LINE}" stroke-width="1.5" rx="12"'
    out.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" {st}/>')
    text(lx if lx is not None else x0 + 14, ly if ly is not None else y0 + 24, label, fs,
         color=HEAD, bold=True, owner=(x0, y0, x1, y1))

def path(name, color, pts):
    paths.append((name, color, pts))

def circle(cx, cy, n, color):
    circles.append((cx, cy, n, color))

def draw_paths():
    for name, color, pts in paths:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        hl, hw = 13, 6.5
        bx, by = x2 - ux * hl, y2 - uy * hl
        d = "M " + " L ".join(f"{x},{y}" for x, y in pts[:-1]) + f" L {bx:.1f},{by:.1f}"
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="3" '
                   f'stroke-dasharray="8 6"/>')
        px, py = -uy, ux
        out.append(f'<polygon points="{x2},{y2} {bx+px*hw:.1f},{by+py*hw:.1f} '
                   f'{bx-px*hw:.1f},{by-py*hw:.1f}" fill="{color}"/>')

def draw_circle(cx, cy, n, color):
    c = GREEN_T if color == GREEN else color
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#ffffff" stroke="{c}" stroke-width="2.5"/>')
    out.append(f'<text x="{cx}" y="{cy+5.5}" font-size="16" font-weight="700" '
               f'text-anchor="middle" fill="{c}">{n}</text>')

# ---------------------------------------------------------------- left diagram
out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')
text(20, 30, "rdp-firefox 工作區模式：一個 Pod、一套 xrdp", 22, HEAD, True)

box("client", 328, 48, 548, 90, "RDP 用戶端（mstsc）")

# namespace web-workspace
frame(20, 112, 900, 736, "namespace web-workspace", "ns", 20, lx=36, ly=154)
box("svc", 318, 126, 558, 166, "Service NodePort 30389")
frame(32, 180, 888, 722, "Pod", "pod", 19, lx=48, ly=204)

# desktop container
frame(44, 216, 876, 510, "desktop（rdp-firefox）", "container", 18, lx=58, ly=240)
box("ttyd2200", 104, 252, 220, 292, "ttyd :2200")
box("xrdp", 380, 252, 496, 292, "xrdp :3389")
box("sesman", 548, 252, 676, 292, "xrdp-sesman")
box("ttyd2210", 712, 252, 828, 292, "ttyd :2210")
frame(90, 312, 790, 496, "桌面 session", "session", 18, lx=106, ly=352)
box("openbox", 250, 326, 350, 366, "openbox")
box("fcitx5", 370, 326, 460, 366, "fcitx5")
box("firefox", 676, 326, 776, 366, "Firefox")
box("xorg", 104, 384, 776, 424, "Xorg :N")
box("btn", 405, 442, 505, 482, "卡片畫面")
box("bar", 530, 442, 620, 482, "工具列")

# jupyter container (left), vscode container (right)
frame(90, 528, 350, 708, "jupyter（rdp-jupyter）", "container", 18, lx=104, ly=554)
box("l2", 236, 566, 336, 606, "啟動服務")
box("jup", 104, 654, 336, 694, "JupyterLab Desktop")
frame(560, 528, 800, 708, "vscode（rdp-vscode）", "container", 18, lx=574, ly=554)
box("l1", 574, 566, 674, 606, "啟動服務")
box("vsc", 574, 654, 724, 694, "VSCodium")
# shared resources
box("sock", 377, 558, 533, 614, None, fs=17, lines=["通訊目錄", "（unix socket）"])
box("home", 405, 654, 505, 694, "/home")

# namespace taroko
frame(20, 750, 900, 946, "namespace taroko", "ns", 20, lx=36, ly=780)
box("svc2", 656, 864, 876, 904, "Service tkadm :22100", fs=17)
frame(196, 792, 600, 932, "Pod tkadm", "pod", 19, lx=210, ly=816)
frame(210, 828, 394, 918, "dkreg", "container", 18, lx=224, ly=852)
box("registry", 224, 864, 380, 904, "registry :5000")
frame(408, 828, 586, 918, "tkadm", "container", 18, lx=422, ly=852)
box("sshd", 422, 864, 572, 904, "sshd :22100")

# ---------------------------------------------------------------- paths
path("1a client-svc", PURPLE, [(438, 90), (438, 126)])
path("1b svc-xrdp", PURPLE, [(438, 166), (438, 252)])
path("2a xrdp-sesman", PURPLE, [(496, 272), (548, 272)])
path("2b sesman-xorg", PURPLE, [(612, 292), (612, 384)])
path("6 vsc-xorg", PURPLE, [(724, 674), (814, 674), (814, 404), (776, 404)])
path("6 jup-xorg", PURPLE, [(104, 674), (66, 674), (66, 404), (104, 404)])
path("4a btn-sock", GREEN, [(455, 482), (455, 558)])
path("4b sock-l1", GREEN, [(533, 586), (574, 586)])
path("4c sock-l2", GREEN, [(377, 586), (336, 586)])
path("5 l1-vsc", GREEN, [(624, 606), (624, 654)])
path("5 l2-jup", GREEN, [(286, 606), (286, 654)])
path("7a ff-ttyd", GREEN, [(744, 326), (744, 292)])
path("7b ttyd-svc2", GREEN, [(828, 272), (850, 272), (850, 864)])
path("7c svc2-sshd", GREEN, [(656, 884), (572, 884)])
path("7d vsc-svc2", GREEN, [(700, 694), (700, 864)])

circle(572, 69, 1, PURPLE)
circle(356, 272, 1, PURPLE)
circle(522, 244, 2, PURPLE)
circle(586, 346, 2, PURPLE)
circle(381, 462, 3, PURPLE)
circle(482, 534, 6, GREEN)
circle(650, 630, 7, GREEN)
circle(260, 630, 7, GREEN)
circle(762, 630, 8, PURPLE)
circle(128, 630, 8, PURPLE)
circle(652, 346, 4, GREEN)
circle(726, 808, 9, GREEN)
circle(824, 808, 5, GREEN)
circle(628, 856, 5, GREEN)

draw_paths()
for c in circles:
    draw_circle(*c)

# ---------------------------------------------------------------- step panel
PX0, PX1, PY0, PY1 = 930, 1420, 52, 946
panel_texts_start = len(texts)
out.append(f'<rect x="{PX0}" y="{PY0}" width="{PX1-PX0}" height="{PY1-PY0}" rx="8" '
           f'fill="#ffffff" stroke="#d4d4d8" stroke-width="1"/>')
text(952, 94, "步驟", 20, HEAD, True)
for i, (col, s) in enumerate([(PURPLE, "畫面：RDP 進來、視窗畫到 Xorg"),
                              (GREEN, "控制：啟動請求、SSH")]):
    y = 82 + i * 30
    out.append(f'<path d="M 1040,{y} L 1088,{y}" stroke="{col}" stroke-width="3" '
               f'stroke-dasharray="8 6" fill="none"/>')
    text(1100, y + 5.5, s, 16, TXT)

steps = [
    (1, PURPLE, "RDP 連線進來", ["mstsc → 節點 IP:30389 → xrdp :3389"]),
    (2, PURPLE, "登入並啟動桌面", ["xrdp-sesman 驗證帳號，啟動 Xorg :N"]),
    (3, PURPLE, "桌面先顯示三張卡片", ["tkadm、VSCodium、JupyterLab；之後用工具列切換"]),
    (4, GREEN, "按 tkadm", ["Firefox 開啟 http://localhost:2210，接到 ttyd :2210"]),
    (5, GREEN, "連到 tkadm", ["ttyd 執行 ssh → tkadm.taroko:22100 的 sshd"]),
    (6, GREEN, "按 VSCodium 或 JupyterLab", ["請求經 unix socket 送到該 container 的啟動服務"]),
    (7, GREEN, "啟動服務開啟程式", ["以登入者的身分執行，程式留在自己的 container"]),
    (8, PURPLE, "視窗畫回桌面", ["VSCodium、JupyterLab Desktop 畫在 desktop 的 Xorg :N"]),
    (9, GREEN, "VSCodium 連到 tkadm", ["Remote-SSH → tkadm.taroko:22100 的 sshd"]),
]
# uniform row height; long lines verified in the rendered PNG (estimator is conservative)
y = 136
for n, col, l1, l2 in steps:
    out.append(f'<path d="M 952,{y} L 1398,{y}" stroke="#e2e2e5" stroke-width="1"/>')
    h = 81
    base = y + 32
    draw_circle(964, base + 8, n, col)
    text(990, base, l1, 17, HEAD, True)
    for j, s in enumerate(l2):
        text(990, base + 27 + j * 25, s, 16, SUB, check=tw(s, 16) < 410)
    y += h
assert y <= 872, y
out.append(f'<path d="M 952,872 L 1398,872" stroke="#e2e2e5" stroke-width="1"/>')
text(952, 900, "整個 Pod 只有 desktop 這個 container 有 xrdp", 15, SUB)

# ---------------------------------------------------------------- checks
errs = []
def seg_rect(a, b, r, shrink=0.5):
    """axis-aligned segment vs rect interior overlap"""
    x0, y0, x1, y1 = r[0] + shrink, r[1] + shrink, r[2] - shrink, r[3] - shrink
    sx0, sx1 = sorted((a[0], b[0])); sy0, sy1 = sorted((a[1], b[1]))
    return sx0 < x1 and sx1 > x0 and sy0 < y1 and sy1 > y0 if (sx0 != sx1 or sy0 != sy1) else False
def seg_rect_touch(a, b, r, pad):
    x0, y0, x1, y1 = r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad
    sx0, sx1 = sorted((a[0], b[0])); sy0, sy1 = sorted((a[1], b[1]))
    return sx0 <= x1 and sx1 >= x0 and sy0 <= y1 and sy1 >= y0
def segs(pts):
    return list(zip(pts[:-1], pts[1:]))
def seg_seg(a, b, c, d):
    ax0, ax1 = sorted((a[0], b[0])); ay0, ay1 = sorted((a[1], b[1]))
    cx0, cx1 = sorted((c[0], d[0])); cy0, cy1 = sorted((c[1], d[1]))
    p = 4
    return ax0 - p <= cx1 and ax1 + p >= cx0 and ay0 - p <= cy1 and ay1 + p >= cy0
def circ_rect(cx, cy, r, rect):
    nx = min(max(cx, rect[0]), rect[2]); ny = min(max(cy, rect[1]), rect[3])
    return (nx - cx) ** 2 + (ny - cy) ** 2 < r * r
def circ_seg(cx, cy, r, a, b):
    return circ_rect(cx, cy, r, (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))

for name, _, pts in paths:
    for a, b in segs(pts):
        assert a[0] == b[0] or a[1] == b[1], name
        for bn, r in leaf.items():
            if seg_rect(a, b, r):
                errs.append(f"path {name} passes through box {bn}")
        for t in texts:
            if seg_rect_touch(a, b, t[:4], 3):
                errs.append(f"path {name} touches text {t[4]}")
        # running along a frame border
        for f in frames:
            for e in [((f[0], f[1]), (f[2], f[1])), ((f[0], f[3]), (f[2], f[3])),
                      ((f[0], f[1]), (f[0], f[3])), ((f[2], f[1]), (f[2], f[3]))]:
                horiz_e = e[0][1] == e[1][1]; horiz_s = a[1] == b[1]
                if horiz_e == horiz_s and seg_seg(a, b, e[0], e[1]) and \
                   abs((a[1] - e[0][1]) if horiz_s else (a[0] - e[0][0])) < 10:
                    errs.append(f"path {name} runs along frame border {f}")
for i in range(len(paths)):
    for j in range(i + 1, len(paths)):
        for a, b in segs(paths[i][2]):
            for c, d in segs(paths[j][2]):
                if seg_seg(a, b, c, d):
                    errs.append(f"paths {paths[i][0]} / {paths[j][0]} intersect or touch")
for cx, cy, n, _ in circles:
    for name, _, pts in paths:
        for a, b in segs(pts):
            if circ_seg(cx, cy, R + 6, a, b):
                errs.append(f"circle {n}@({cx},{cy}) too close to path {name}")
    for bn, r in leaf.items():
        if circ_rect(cx, cy, R + 6, r):
            errs.append(f"circle {n}@({cx},{cy}) too close to box {bn}")
    for t in texts[:panel_texts_start]:
        if circ_rect(cx, cy, R + 4, t[:4]):
            errs.append(f"circle {n}@({cx},{cy}) too close to text {t[4]}")
    for f in frames:
        inside = f[0] + R + 5 <= cx <= f[2] - R - 5 and f[1] + R + 5 <= cy <= f[3] - R - 5
        outside = not circ_rect(cx, cy, R + 5, f)
        if not (inside or outside):
            errs.append(f"circle {n}@({cx},{cy}) overlaps frame border {f}")
for i, (ax, ay, an, _) in enumerate(circles):
    for bx, by, bn, _ in circles[i + 1:]:
        if (ax - bx) ** 2 + (ay - by) ** 2 < (2 * R + 6) ** 2:
            errs.append(f"circles {an}/{bn} overlap")
for t in texts:
    if t[5]:
        o = t[5]
        if t[0] < o[0] + 4 or t[2] > o[2] - 4 or t[1] < o[1] or t[3] > o[3]:
            errs.append(f"text '{t[4]}' exceeds its box ({t[0]:.0f}-{t[2]:.0f} vs {o[0]}-{o[2]})")
    if t[2] > (PX1 - 8 if t[0] >= PX0 else 900) or t[0] < 20:
        errs.append(f"text '{t[4]}' out of area: ends {t[2]:.0f}")
for i in range(len(texts)):
    for j in range(i + 1, len(texts)):
        a, b = texts[i], texts[j]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
            errs.append(f"texts overlap: '{a[4]}' / '{b[4]}'")
# label text vs leaf boxes (frame labels must not be covered by boxes)
for t in texts[:panel_texts_start]:
    for bn, r in leaf.items():
        if t[5] == r:
            continue
        if t[0] < r[2] + 4 and r[0] - 4 < t[2] and t[1] < r[3] and r[1] < t[3]:
            errs.append(f"text '{t[4]}' overlaps box {bn}")
# leaf boxes must not overlap each other
ln = list(leaf.items())
for i in range(len(ln)):
    for j in range(i + 1, len(ln)):
        a, b = ln[i][1], ln[j][1]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
            errs.append(f"boxes overlap: {ln[i][0]} / {ln[j][0]}")

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
       f'font-family="{FONT}">\n' + "\n".join(out) + "\n</svg>\n")
open(OUT, "w", encoding="utf-8").write(svg)
print("written", OUT)
for e in errs:
    print("ERR", e)
print("errors:", len(errs))
