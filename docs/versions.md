# 版本比較

rdp-firefox 各版本映像檔的差異。安裝方式見 [install.md](install.md)。

| | v3.2 | v3.4-share | v3.5-share | v3.6-share | v3.7-share | v3.8-share |
| --- | --- | --- | --- | --- | --- | --- |
| 映像檔 | `ghcr.io/braveantony/rdp-firefox:3.2` | `ghcr.io/braveantony/rdp-firefox:3.4-share` | `ghcr.io/braveantony/rdp-firefox:3.5-share` | `ghcr.io/braveantony/rdp-firefox:3.6-share` | `ghcr.io/braveantony/rdp-firefox:3.7-share` | `ghcr.io/braveantony/rdp-firefox:3.8-share` |
| 同一帳號多人同時登入、各自獨立桌面 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| localhost:2200／2210 Web 終端機 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 分享自己的桌面（操作 PIN／唯讀 PIN） | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| 多個帳號（Secret 帳號檔案） | — | — | ✅ | ✅ | ✅ | ✅ |
| `curl \| bash` 安裝、Kustomize 部署 | — | — | ✅ | ✅ | ✅ | ✅ |
| 桌面內直接輸入中文（新酷音） | — | — | — | ✅ | ✅ | ✅ |
| 2210 免設定直連 tkadm（22100 埠）、設定多個帳號時詢問 SSH 帳號 | — | — | — | — | ✅ | ✅ |
| [工作區模式](workspace-mode.md)（`RDP_MODE=workspace`） | — | — | — | — | — | ✅ |
| 映像檔大小 | 約 790 MB | 約 1.04 GB | 約 1.04 GB | 約 1.08 GB | 約 1.08 GB | 約 1.12 GB |
| 原始碼 | branch [`release/3.2`](../../../tree/release/3.2) | branch [`release/3.4-share`](../../../tree/release/3.4-share) | branch [`release/3.5-share`](../../../tree/release/3.5-share) | branch [`release/3.6-share`](../../../tree/release/3.6-share) | branch [`release/3.7-share`](../../../tree/release/3.7-share) | branch [`release/3.8-share`](../../../tree/release/3.8-share) |

名稱帶 `-share` 的映像檔內建分享桌面的功能，一行指令安裝的就是 `3.8-share`。`images/rdp-firefox/Dockerfile` 用建置參數 `SESSION_SHARE` 區分：`SESSION_SHARE=1` 建出 `-share` 版；`SESSION_SHARE=0`（預設）建出不含分享功能的版本（此版本未另外發布映像檔）。各版本的差異說明見 [Releases](../../../releases)。
