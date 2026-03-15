# Remote Mouse

本文件为 AI 助手及开发者提供项目概览、技术细节和工作流程参考。

## 1. 项目概览
Remote Mouse 是一款轻量级、低延迟的远程控制工具，可将移动设备（iOS/Android）通过浏览器（PWA）变为电脑的无线触控板和键盘。支持 Windows, macOS, 和 Linux。

## 2. 技术栈
- **服务端 (Server)**:
  - 语言: Python 3.13+
  - 核心库: FastAPI (Web 服务), PyAutoGUI (模拟输入), Zeroconf (mDNS 自动发现), pystray (系统托盘), Pillow (图标处理), Loguru (日志)。
  - 包管理: [uv](https://github.com/astral-sh/uv)
- **客户端 (Web Client)**:
  - 语言: TypeScript
  - 框架/工具: Vite, 原生 CSS, Vite-PWA (离线支持)
  - 测试: Vitest

## 3. 架构概览
项目采用经典的 **Client-Server** 架构：
- **服务端**: 运行多线程服务。`ServiceManager` 管理 Uvicorn (HTTP/WebSocket) 和 mDNS 响应器的生命周期。`TrayIcon` 在主线程运行，提供 UI 交互。
- **客户端**: 响应式 Web 应用。`transport.ts` 处理与服务端的二进制通信，`touchpad.ts` 和 `keyboard.ts` 捕获用户输入并封装为协议指令。

### 服务端进程/线程模型
服务端采用 **单进程、多线程** 模型：
- **主线程 (Main Thread)**: 运行 `pystray` 托盘 UI 循环。
- **服务线程 (Service Thread)**: 由 `ServiceManager` 启动的守护线程，运行 `uvicorn` (FastAPI) 实例。负责处理 WebSocket 通信、静态文件托管以及调用 `PyAutoGUI` 模拟输入。
- **监控线程 (Monitor Thread)**: 可选线程。当开启“速率显示”时，定时计算每秒包数 (PPS) 和比特率 (BPS)，并动态生成图标更新主线程的托盘显示。
- **并发处理**: 网络 IO 部分基于 Python 的 `asyncio`，而 UI 与背景任务则通过多线程实现物理隔离。

## 4. 目录地图
```text
.
├── server/                 # Python 服务端
│   ├── src/server/
│   │   ├── core/           # 核心逻辑 (协议定义、指标监控)
│   │   ├── services/       # 后台服务 (Web, mDNS, Manager)
│   │   ├── ui/             # 系统托盘 UI
│   │   └── main.py         # 运行入口
│   └── tests/              # 服务端单元测试
├── web-client/             # TypeScript 客户端
│   ├── src/
│   │   ├── core/           # 协议与传输层
│   │   ├── input/          # 输入捕获 (Touchpad, Scroll, Keyboard)
│   │   └── ui/             # UI 组件 (Settings, Status Bar)
│   └── tests/              # 客户端单元测试
└── requirement/            # 需求文档 (v1~v3)
```

## 5. 核心接口 (二进制协议)
客户端通过 WebSocket 发送二进制指令。指令格式：`[OpCode (1B)] [Payload]`

| OpCode | 指令 | Payload 格式 | 说明 |
| :--- | :--- | :--- | :--- |
| `0x01` | Move | `dx(2B), dy(2B)` | 相对位移 (Big-endian signed short) |
| `0x02` | Click | `button(1B), mask(1B)` | button: 1-左, 2-右; mask: 修饰键位掩码 |
| `0x03` | Scroll | `sx(2B), sy(2B)` | 滚动量 |
| `0x04` | Drag | `state(1B)` | 0x01-按下, 0x00-释放 |
| `0x05` | Text | `UTF8 String` | 文本输入 (通过剪贴板中转以支持多语言) |
| `0x06` | Key | `mask(1B), key_name(UTF8)` | 特殊键 (Enter, Backspace 等) |

**修饰键位掩码 (Modifier Mask):**
- Bit 0: Ctrl, Bit 1: Shift, Bit 2: Alt, Bit 3: Win/Cmd

## 6. 常用快速命令
### 服务端 (server/)
- **同步依赖**: `uv sync`
- **开发运行**: `uv run python -m server.main` (可带 `--port`, `--log`)
- **静态检查**: `uv run ruff check .`
- **代码 lint**: `uv run ruff format`
- **运行测试**: `uv run pytest`

### 客户端 (web-client/)
- **安装依赖**: `npm install`
- **开发模式**: `npm run dev`
- **构建打包**: `npm run build` (产物由 Python 服务端自动托管)
- **运行测试**: `npm run test`

## 7. 开发规约与技巧

### 如何添加新功能（扩展协议）
若需添加新的控制指令（如多媒体控制）：
1. **定义 OpCode**: 在 `server/src/server/core/protocol.py` 和 `web-client/src/core/protocol.ts` 中同步定义新的 `OP_XXX` 常量。
2. **客户端实现**: 在 `web-client/src/input/` 下相关组件中捕获输入，调用 `transport.send()` 发送二进制数据。
3. **服务端实现**: 在 `server/src/server/core/protocol.py` 的 `process_binary_command` 函数中添加对应的 `elif opcode == OP_XXX` 分支逻辑。

### 静态文件托管
- **生产/常规模式**: 服务端会自动寻找 `web-client/dist` 目录并托管。因此，修改客户端代码后需运行 `npm run build` 才能在 `uv run python -m server.main` 中看到变化。
- **开发模式**: 建议分别启动 `npm run dev`（前端热更新）和服务端。

### 日志
- 服务端使用 `loguru`。开发时建议开启 `--log` 参数以启用详细日志记录。
- 关键逻辑（如输入模拟失败）应使用 `logger.error` 或 `logger.warning`。

## 8. Git Commit 规范
遵循 **Conventional Commits** 风格：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码格式 (不影响逻辑)
- `refactor`: 重构
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动

示例: `feat: add real-time rate monitoring`
