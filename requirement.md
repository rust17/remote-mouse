# Remote Mouse 产品需求文档 (PRD)

**版本**: 1.0 (MVP Implementation)
**状态**: 已实现

## 1. 产品概述
Remote Mouse 是一款简洁的局域网远程控制工具，旨在将用户的智能手机（iOS/Android）转化为电脑（Windows/macOS/Linux）的无线触摸板与键盘。通过 WiFi 网络，用户可以远程控制鼠标光标、执行点击、滚动页面以及进行文本输入。

## 2. 核心功能 (User Stories)

### 2.1 设备连接与发现
*   **自动扫描**: 用户打开 App，系统自动扫描局域网内开启服务的电脑。
    *   *技术细节*: UDP 广播 (端口 9999)，消息内容 "SCAN_REMOTE_MOUSE"。
*   **手动刷新**: 用户可通过右上角刷新按钮重新发起扫描。
*   **设备列表**: 显示已发现设备的 Hostname 和 IP。
*   **快速连接**: 点击设备项，建立低延迟 TCP 连接 (端口 9998)。状态栏实时显示连接状态 ("已连接", "断开", "错误")。

### 2.2 鼠标控制体验
界面主体分为触摸板和功能键区：
*   **光标移动**:
    *   在触摸板区域单指滑动，控制电脑光标移动。
    *   *灵敏度*: 默认 2.0 倍率。
*   **点击操作**:
    *   **触摸板点击**: 单指轻触触摸板区域，触发鼠标**左键单击**。
    *   **独立按键**: 屏幕下方提供独立的“左键”和“右键”触控区。
*   **滚轮滚动**:
    *   提供独立的垂直滚动条区域（位于左右键之间）。
    *   上下拖动该区域模拟滚轮滚动。

### 2.3 键盘与输入
*   **文本传输**:
    *   点击键盘图标唤起手机原生输入法。
    *   支持中英文输入，字符实时同步至电脑。
    *   支持退格键 (Backspace) 删除操作。
*   **功能按键 (Function Keys)**:
    *   **Esc**: 单击直接发送 Esc 指令。
*   **修饰键 (Modifier Keys)**:
    *   **Ctrl / Alt**: 采用 **Toggle (切换)** 模式。
        *   点击一次高亮（按下状态），此时输入的字符或点击的鼠标将包含该修饰符（如 Ctrl+C, Ctrl+Click）。
        *   再次点击取消高亮（释放状态）。
    *   *注*: Shift 和 Win/Cmd 键目前代码中存在逻辑支持，但暂未添加到 UI 布局中。

## 3. 技术规格与协议

### 3.1 架构
*   **Client (Mobile)**: Flutter。使用 `RawDatagramSocket` 进行发现，`Socket` 进行长连接控制。
*   **Server (Desktop)**: Python。使用 `socket` 库通信，`pyautogui` 执行系统级输入模拟。

### 3.2 通信协议
*   **发现协议 (UDP)**:
    *   Client -> Broadcast (9999): `SCAN_REMOTE_MOUSE`
    *   Server -> Client: `{"hostname": "...", "ip": "...", "port": 9998}`
*   **控制协议 (TCP)**:
    *   连接至端口 9998，禁用 Nagle 算法 (`TCP_NODELAY`)。
    *   指令格式: JSON 对象 + `\n` (换行符) 分隔。
    *   **指令集**:
        *   `{"type": "move", "dx": int, "dy": int}`
        *   `{"type": "click", "button": "left"|"right"}`
        *   `{"type": "scroll", "amount": int}`
        *   `{"type": "text", "text": string}`
        *   `{"type": "key", "key": string}` (e.g., "backspace", "esc")
        *   `{"type": "keyDown"|"keyUp", "key": string}` (e.g., "ctrl", "alt")

## 4. 界面布局规范 (UI Specs)

```text
[ AppBar: Title & Status | Refresh Icon ]
+---------------------------------------+
|                                       |
|                                       |
|             触摸板区域                 |
|         (Touchpad Area)               |
|       Gestures: Pan, Tap              |
|                                       |
|                                       |
+---------------------------------------+
|  Left Click |   Scroll    | Right Click |
|   (Button)  |   (Strip)   |  (Button)   |
+---------------------------------------+
| [Esc]  [Ctrl]  [Alt]   [Keyboard Icon]|
+---------------------------------------+
```
