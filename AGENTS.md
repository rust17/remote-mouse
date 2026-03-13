# Remote Mouse

## 1. 项目概述
Remote Mouse 是一个轻量级、低延迟的远程控制工具，允许通过移动设备（浏览器/PWA）作为触控板和键盘控制桌面计算机（Windows/macOS/Linux）。

## 2. 技术架构
项目采用 **Client-Server (C/S)** 架构：
- **Web Client (移动端)**: 作为控制端，运行在手机浏览器中，通过 WebSocket 发送控制指令。
- **Python Server (桌面端)**: 作为被控端，接收并执行指令，同时通过 HTTP 提供 Web 客户端的静态资源服务。

### 通信机制
- **传输层**: WebSocket (低延迟双向通信)。
- **协议格式**: **自定义二进制协议**。使用 ArrayBuffer 封装指令，最大限度减少传输负载。
- **服务发现**: 使用 **mDNS (Zeroconf)** 协议，使客户端在局域网内能自动发现服务端地址。

## 3. 技术栈组成
### 服务端 (Python)
- **核心语言**: Python 3.13+
- **Web 框架**: FastAPI (处理 HTTP 静态资源和 WebSocket)
- **输入模拟**: PyAutoGUI (控制鼠标移动、点击、滚动及按键)
- **自动发现**: Zeroconf (mDNS 服务端注册)
- **系统托盘**: Pystray (提供桌面退出、重启、日志查看等交互)
- **包管理**: UV (高性能 Python 包管理器)
- **日志记录**: Loguru
- **剪贴板操作**: Pyperclip (用于支持多语言/表情文本输入)

### 客户端 (TypeScript)
- **构建工具**: Vite
- **核心语言**: TypeScript
- **界面开发**: CSS + PWA (Progressive Web App)
- **手势识别**: 原生 Touch 事件监听与逻辑计算

## 4. 模块组成
### 服务端 (server/src/server/)
- `core/protocol.py`: **核心协议解析器**。定义操作码（Move, Click, Scroll, Text 等）并调用 PyAutoGUI 执行。
- `services/web.py`: **Web 服务**。集成 FastAPI，挂载静态文件并维护 `/ws` 端点。
- `services/mdns.py`: **自动发现服务**。注册 `_http._tcp.local.` 服务。
- `services/manager.py`: **服务生命周期管理**。统一启动/停止 Web 和 mDNS 服务。
- `ui/tray_icon.py`: **托盘交互**。提供 GUI 控制入口。

### 客户端 (web-client/src/)
- `core/transport.ts`: **传输管理**。维护 WebSocket 连接与自动重连逻辑。
- `input/touchpad.ts`: **触控板逻辑**。将单指移动、双指点击、三指拖拽转换为二进制指令。
- `input/keyboard.ts`: **键盘逻辑**。处理文本输入（通过剪贴板）和功能键按下。
- `input/scroll-strip.ts`: **滚动逻辑**。处理侧边滚动条手势。

## 5. 接口与协议 (API/Protocol)
### WebSocket 二进制协议 (`/ws`)
指令格式：`[OpCode (1B)] [Data (NB)]`
- `0x01 (MOVE)`: `[dx (short)] [dy (short)]` (相对位移)
- `0x02 (CLICK)`: `[button (1B)] [modifier_mask (1B)]` (左/右键及修饰键)
- `0x03 (SCROLL)`: `[sx (short)] [sy (short)]` (横向/纵向滚动)
- `0x04 (DRAG)`: `[state (1B: 0/1)]` (鼠标左键按下/释放)
- `0x05 (TEXT)`: `[utf8_payload]` (文本内容，通过粘贴实现)
- `0x06 (KEY)`: `[modifier_mask (1B)] [key_name (utf8)]` (功能键按压)

## 6. 目录地图 (Directory Map)
```text
remote-mouse/
├── requirement/          # 需求文档与迭代计划 (v1-v4)
├── server/               # 服务端代码
│   ├── src/server/
│   │   ├── core/         # 协议解析逻辑
│   │   ├── services/     # Web/mDNS 核心服务
│   │   ├── ui/           # 托盘 UI 代码
│   │   └── main.py       # 程序入口
│   └── pyproject.toml    # Python 依赖管理 (UV)
├── web-client/           # 客户端代码
│   ├── src/
│   │   ├── core/         # WebSocket 传输层
│   │   ├── input/        # 手势与键盘输入逻辑
│   │   ├── ui/           # UI 组件 (设置、状态栏)
│   │   └── main.ts       # 客户端入口
│   ├── package.json      # 前端依赖管理
│   └── vite.config.ts    # 构建配置 (含 PWA 插件)
└── README.md             # 项目主说明文档
```

## 7. 核心原理
1. **多指手势映射**: 客户端监听 Touch 事件，计算坐标差值（Delta），封装为二进制包发送。
2. **文本支持**: 由于 PyAutoGUI 直接 `write` 对中文支持不佳，服务端采用“设置剪贴板+触发粘贴热键（Cmd/Ctrl + V）”的方式实现。
3. **零配置接入**: mDNS 允许手机在同一 WiFi 下直接访问 `http://remote-mouse.local:9997` 而无需手动输入 IP。
