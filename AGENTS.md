# Remote Mouse

## 1. 项目概述
Remote Mouse 是一个轻量级、低延迟的远程控制工具，允许通过移动设备（浏览器/PWA）作为触控板和键盘控制桌面计算机（Windows/macOS/Linux）。

## 2. 技术架构
项目采用 **Client-Server (C/S)** 架构：
- **Web Client (控制端)**: 运行在移动端浏览器中，作为 PWA 应用通过 WebSocket 发送控制指令。
- **Rust Server (被控端)**: 基于 **Tauri v2** 构建的纯托盘后台服务。它集成了一个高性能的 Web 服务器，执行指令并提供静态资源。

## 3. 技术栈组成
### 服务端 (Rust / Tauri v2)
- **核心框架**: Tauri v2 (纯托盘模式，无窗口，低内存占用)
- **Web 服务**: Axum (高性能异步 Web 框架，处理 HTTP/WebSocket)
- **输入模拟**: Enigo (跨平台原生输入控制)
- **服务发现**: mdns-sd (异步 mDNS 注册与发现)
- **异步运行时**: Tokio

### 客户端 (TypeScript / Vite)
- **构建工具**: Vite
- **核心语言**: TypeScript
- **界面开发**: 原生 CSS + PWA (Progressive Web App)

## 4. 模块组成
### 服务端 (server/src/)
- `main.rs`: **程序入口**。配置 Tauri 事件循环、托盘菜单、以及跨平台策略。
- `core/protocol.rs`: **协议解析**。处理二进制指令流，并将其分发给输入 Worker。
- `services/input.rs`: **输入执行器**。封装 Enigo 操作。
- `services/web.rs`: **Web 服务引擎**。使用 Axum 提供静态文件托管（基于 `rust-embed`）和 WebSocket 指令接收。
- `services/mdns.rs`: **自动发现服务**。注册 `_remote-mouse._tcp.local.` 服务。

## 5. 命令 (Commands)

### 开发与环境配置
**1. Web 客户端**
客户端资源会被嵌入到 Rust 二进制文件中。首先构建客户端：
```bash
cd web-client
npm install
npm run build
```

**2. 服务端**
使用开发模式运行（需安装 [Tauri CLI](https://tauri.app/v2/guides/development/getting-started/))：
```bash
cd server
cargo tauri dev
```

打包生产版本安装程序：
```bash
cd server
cargo tauri build
```

## 6. 接口与协议 (API/Protocol)
### WebSocket 二进制协议 (`/ws`)
指令格式：`[OpCode (1B)] [Data (NB)]`
- `0x01 (MOVE)`: `[dx (short)] [dy (short)]` (相对位移)
- `0x02 (CLICK)`: `[button (1B)] [modifier_mask (1B)]` (左/右键及修饰键)
- `0x03 (SCROLL)`: `[sx (short)] [sy (short)]` (横向/纵向滚动)
- `0x04 (DRAG)`: `[state (1B: 0/1)]` (鼠标左键按下/释放)
- `0x05 (TEXT)`: `[utf8_payload]` (文本字符串内容)
- `0x06 (KEY)`: `[modifier_mask (1B)] [key_name (utf8)]` (功能键按压)

## 7. 目录地图 (Directory Map)
```text
remote-mouse/
├── requirement/          # 需求文档与迭代计划 (v1-v4)
├── server/               # Rust 服务端代码 (Tauri v2)
│   ├── src/
│   │   ├── core/         # 协议解析逻辑
│   │   ├── services/     # Web/mDNS/Input 核心服务
│   │   └── main.rs       # Tauri 应用入口与托盘配置
│   ├── assets/           # 跨平台图标资源 (.ico, .icns, .png)
│   ├── Cargo.toml        # Rust 依赖配置
│   └── tauri.conf.json   # Tauri 构建与分发配置
├── web-client/           # Web 客户端代码 (控制端)
├── server-py/            # (Legacy) 旧版 Python 服务端备份
└── README.md             # 项目说明文档
```

## 8. 核心原理
1. **多线程解耦**: 使用 Tokio 异步处理网络 IO，独立线程处理同步系统调用，确保托盘和网络响应流畅。
2. **纯净后台体验**: 通过 `LSUIElement` (macOS) 和 `windows_subsystem` 配置，应用作为真正的系统级工具运行。
3. **嵌入式资源**: 通过 `rust-embed` 将静态网页嵌入二进制，实现单文件分发。
4. **零配置接入**: 客户端通过 mDNS 自动发现服务端。
