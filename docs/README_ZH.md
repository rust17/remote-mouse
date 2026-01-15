# <img src="remote-mouse-icon.jpg" width="32" style="border-radius: 20%;" /> Remote Mouse

[English](../README.md) | [简体中文](README_ZH.md)

<p align="center">
  <img src="remote-mouse.png" alt="Remote Mouse" width="300" />
</p>

---

Remote Mouse 是一款轻量级、低延迟的远程控制工具，可将您的移动设备（iOS/Android）转变为电脑（Windows/macOS/Linux）的无线触摸板和键盘。

### 功能特性

- **PWA 支持**: 可将 Web 客户端作为原生应用安装到手机，享受全屏操作体验。
- **自动发现**: 使用 mDNS 技术自动发现局域网内的服务器。
- **灵敏触摸板**: 低延迟光标控制，支持灵敏度调节。
- **全键盘输入**: 支持文本输入、功能键（Esc、Tab、Enter）以及修饰键（Ctrl、Alt、Shift、Win）。
- **现代 UI**: 采用深色模式和精致的半透明毛玻璃视觉设计。
- **跨平台**: 服务端基于 Python，客户端可在任何现代移动浏览器中运行。

### 下载与运行 (普通用户)

请前往 [Releases](https://github.com/rust17/remote-mouse/releases) 页面下载最新版本。

#### Windows
1. 下载 `RemoteMouse.exe`。
2. **右键点击**并选择 **“以管理员身份运行”**（这是控制高权限应用所必需的）。
3. 如果 Windows 防火墙提示，请允许访问。

#### macOS
1. 下载 `RemoteMouse` 文件。
2. 打开终端并授予执行权限：
   ```bash
   chmod +x ~/Downloads/RemoteMouse
   ```
3. 在访达 (Finder) 中右键点击该文件并选择“打开”。
4. **授予权限**：前往 `系统设置` > `隐私与安全性` > `辅助功能`，添加并启用 `RemoteMouse`。若不开启此权限，服务端将无法控制光标。

---

### 开发指南

#### 技术栈
- **服务端**: Python 3.12+, FastAPI, PyAutoGUI, Zeroconf, uv
- **Web 客户端**: TypeScript, Vite, PWA

#### 环境设置

**1. 服务端**
```bash
cd server
# 使用 uv 安装依赖
uv sync
# 运行服务端
uv run python -m server.main
```

**2. Web 客户端**
```bash
cd web-client
npm install
npm run build
# 客户端文件会自动由 Python 服务端托管，
# 您也可以在开发模式下运行：
npm run dev
```

### 使用方法
1. 在电脑上启动服务端。
2. 确保您的手机和电脑处于 **同一局域网（Wi-Fi）** 下。
3. 获取访问地址：
   - 推荐地址：**http://remote-mouse.local:9997**
   - 备选地址：右键点击电脑系统托盘的**图标**查看 IP 地址（例如 `http://192.168.1.10:9997`）。
4. 在手机浏览器中打开该地址。
5. (可选) 点击“添加到主屏幕”以作为 PWA 安装。
6. 开始远程控制！
