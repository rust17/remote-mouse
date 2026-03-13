# <img src="remote-mouse-icon.jpg" width="32" style="border-radius: 20%;" /> Remote Mouse

[English](../README.md) | [简体中文](README_ZH.md)

<p align="center">
  <img src="remote-mouse.gif" width="1920" />
</p>

<p align="center">
  <img src="dart.jpg" width="250" />
  <img src="light.jpg" width="250" />
  <img src="light-setting.jpg" width="250" />
</p>

---

Remote Mouse 是一款轻量级、低延迟的远程控制工具，可将您的移动设备（iOS/Android）转变为电脑（Windows/macOS/Linux）的无线触摸板和键盘。

### 功能特性

- **PWA 支持**: 可将 Web 客户端作为原生应用安装到手机，享受全屏操作体验。
- **自动发现**: 使用 mDNS 技术自动发现局域网内的服务器。
- **纯托盘运行**: 作为轻量级后台服务运行，仅在系统托盘显示图标。
- **低延迟**: 高性能 Rust 服务端，确保光标移动与输入响应流畅无阻。
- **全键盘输入**: 支持文本输入、功能键（Esc、Tab、Enter）以及修饰键（Ctrl、Alt、Shift、Win）。
- **跨平台支持**: 基于 Rust 和 Tauri 构建，在 Windows、macOS 和 Linux 上均有出色表现。

### 下载与运行 (普通用户)

请前往 [Releases](https://github.com/rust17/remote-mouse/releases) 页面下载最新版本。

#### Windows
1. 下载 `.msi` 或 `.exe` 安装包。
2. 运行安装程序并启动应用。
3. 在**系统托盘**中找到 Remote Mouse 图标进行控制。

#### macOS
1. 下载 `.dmg` 文件并将 Remote Mouse 拖入“应用程序”文件夹。
2. 启动应用，它将出现在您的**菜单栏**中。
3. **授予权限**：前往 `系统设置` > `隐私与安全性` > `辅助功能`，启用 `Remote Mouse`。若不开启此权限，服务端将无法控制光标和键盘。

#### Linux
1. 下载 `.deb` 包或 `.AppImage` 文件。
2. 安装软件包或赋予 AppImage 执行权限。
3. 启动应用，查看系统托盘。

---

### 开发指南

有关技术细节和开发说明，请参阅 [AGENTS.md](../AGENTS.md)。

### 使用方法
1. 在电脑上启动服务端。
2. 确保您的手机和电脑处于 **同一局域网（Wi-Fi）** 下。
3. 在手机浏览器中打开访问地址：
   - **http://remote-mouse.local:9997**
4. (可选) 点击“添加到主屏幕”以作为 PWA 安装，享受更好的体验。
5. 开始控制！
