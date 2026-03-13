# Remote Mouse 需求文档 V4 (Rust 后端重构)

**版本**: 4.0 (Rust & Enigo Refactor)
**状态**: 规划中
**目标**: 将基于 Python/PyAutoGUI 的服务端完全重构为基于 Rust/Enigo 的原生应用，以实现极致的低延迟、单文件部署和更低的资源占用。同时保持原有 Web Client 和通信协议的 100% 兼容。

---

## 阶段 1: 基础工程搭建 (Project Setup)
- [x] **初始化 Rust 项目**: 在 `server` 目录下初始化 Cargo 项目（或替换原 Python 目录）。
- [x] **配置核心依赖**:
  - 异步/Web: `tokio`, `axum`, `axum` 自带的 `ws`
  - 输入控制: `enigo`
  - 服务发现: `mdns-sd` 或 `zeroconf` (Rust版)
  - 托盘图标: `tray-icon`, `tao` (用于主线程事件循环)
  - 静态资源: `rust-embed` (用于打包前端产物)
  - 字节解析: `bytes`, `byteorder`
- [x] **构建脚本配置 (`build.rs`)**: 配置 Windows/macOS 的应用图标和应用清单 (Manifest)。

## 阶段 2: 核心输入控制层 (Input Simulation)
> **注意**: 为防止阻塞 Web 服务器的异步线程，输入控制逻辑需运行在独立的 `std::thread` 中，或使用 `tokio::task::spawn_blocking`。

- [x] **封装 `MouseController`**:
  - [x] 实现相对移动 (Move)
  - [x] 实现鼠标点击 (Click - Left/Right/Middle)
  - [x] 实现鼠标拖拽按下与释放 (Drag Start/End)
  - [x] 实现滚轮滚动 (Scroll - 垂直/水平)
- [x] **封装 `KeyboardController`**:
  - [x] 实现纯文本输入 (处理 UTF-8，考虑 Enigo 的 `text` 方法或剪贴板 fallback)
  - [x] 实现功能键映射 (映射前端传来的 `"enter"`, `"backspace"`, `"esc"` 等至 Enigo 的 `Key` 枚举)
  - [x] 实现修饰键 (Modifier Keys) 状态管理，解析位掩码 (Bitmask: Ctrl/Shift/Alt/Win) 并包裹执行目标按键/点击。
- [x] **系统权限处理 (macOS)**: 编写文档或提示，引导用户在 macOS 开启辅助功能权限；处理没有权限时的容错。

## 阶段 3: 二进制协议解析层 (Protocol Parser)
> **参考 `v3_1.md` - `v3_3.md`**, 保持大端序 (Big-Endian) 解析。

- [x] **定义指令结构体 (Enums/Structs)**: 将接收到的二进制流映射为强类型的 Rust 枚举。
- [x] **解析 `Move (0x01)`**: `[OpCode: 1B] [DeltaX: Int16] [DeltaY: Int16]`
- [x] **解析 `Click (0x02)`**: `[OpCode: 1B] [Button: 1B] [ModifierMask: 1B]` (V3.3 新增掩码)
- [x] **解析 `Scroll (0x03)`**: `[OpCode: 1B] [ScrollX: Int16] [ScrollY: Int16]`
- [x] **解析 `Drag (0x04)`**: `[OpCode: 1B] [State: 1B]`
- [x] **解析 `Text (0x05)`**: `[OpCode: 1B] [UTF-8 Bytes...]`
- [x] **解析 `KeyAction (0x06)`**: `[OpCode: 1B] [ModifierMask: 1B] [KeyName: UTF-8 Bytes...]`

## 阶段 4: Web 服务与网络层 (Server & mDNS)
- [x] **HTTP 服务 (Axum)**:
  - 拦截 `/` 以及静态资源路径，使用 `rust-embed` 从内存中提供 `web-client/dist` 目录下的编译产物。
- [x] **WebSocket 接口 (`/ws`)**:
  - 接收来自客户端的二进制 `Message::Binary`。
  - 将字节流喂给“协议解析层”。
  - 将解析出的控制指令通过 `mpsc::channel` 发送给“输入控制层”执行。
  - 处理断开连接时的状态重置（释放可能处于按下状态的按键或拖拽状态）。
- [x] **mDNS 广播**:
  - 启动时获取本机局域网 IP。
  - 注册 `_http._tcp` 或自定义服务类型，广播主机名（如 `remote-mouse.local`）和端口。

## 阶段 5: 托盘程序与线程模型 (System Tray & Lifecycle)
> **关键架构**: GUI 事件循环必须在主线程 (Main Thread) 运行。

- [x] **主线程 (Main Thread)**:
  - 初始化系统托盘图标 (System Tray)。
  - 提供简单的右键菜单 (Status: 服务运行中, Exit: 退出程序)。
  - 启动 GUI 阻塞式事件循环 (`EventLoop::run`)。
- [x] **后台线程 (Background Runtime)**:
  - 在主线程启动前，使用 `std::thread::spawn` 启动一个挂载了 `tokio::Runtime` 的独立线程。
  - 在 Tokio 运行时中跑 Axum Server 和 mDNS 服务。

## 阶段 6: 联调、测试与 CI/CD 构建
- [ ] **前端联调测试**: 运行现有的 Web Client，通过手机或浏览器进行端到端全手势测试，对比 Python 版本的延迟。
- [ ] **单元测试替换**: 将原本 Python 中的协议解析测试用 Rust 编写 (`#[cfg(test)]`)。
- [ ] **打包策略优化**: 确保 `cargo build --release` 能够一次性将前端前端资源编译并打包进单一可执行文件中。
- [ ] **CI 流水线更新**: 更新 `.github/workflows`，使用 Rust 工具链编译 macOS, Windows, Linux 产物，替换原有的 Python 打包工具 (PyInstaller/Nuitka)。