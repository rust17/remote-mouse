# 打包与发布

打包后，用户无需安装 Python 或 Node.js，下载对应系统的文件即可使用。

## 本地打包

先安装 **Node.js 22、uv 和 Python 3.13**，在仓库根目录运行：

```bash
uv run --frozen --project server python packaging/build.py
```

脚本会自动安装依赖、构建网页，再打包电脑端。它只为当前电脑的系统和芯片打包；同一平台的旧构建文件会被替换。

| 系统 | 额外要求 | 打包结果 |
| --- | --- | --- |
| macOS | 使用系统自带工具 | DMG，内含 RemoteMouse.app |
| Windows | 安装 Inno Setup 6.4+（6.x），使用 x64 Python | 安装器和免安装 ZIP |
| Linux | 使用 Ubuntu 22.04 x64、X11 桌面 | tar.gz 压缩包 |

结果在 `packaging/out/<平台>-<架构>/products/`。不指定版本时，文件名会带上开发版本和提交编号。

需要指定版本，可以加 `--version`；这只改变打包版本，不会发布：

```bash
uv run --frozen --project server python packaging/build.py --version 1.2.3
```

Linux 所需依赖可这样安装；没有桌面环境时，在构建命令前加 `xvfb-run -a`：

```bash
sudo apt-get install xvfb xauth libx11-6 libxtst6 xclip pulseaudio-utils
```

系统音量依赖：macOS 使用系统 `osascript`（先通过 Core Audio 检查默认输出设备）；Windows 的 `pycaw` / `comtypes` 仅在 Windows 安装，并由冻结配置收集；Linux 需安装 `pactl`（`pulseaudio-utils`），运行 PulseAudio 或 PipeWire 的 `pipewire-pulse` 兼容服务。音频依赖、权限或输出设备不可用时只禁用受影响的媒体控制。

## 检查打包结果

运行测试：

```bash
uv run --frozen --project server pytest server/src/tests packaging/tests
```

以 macOS M 系列芯片为例，下面的命令会启动打包后的程序，检查网页和连接，再关闭程序，不会操作鼠标和键盘：

```bash
uv run --frozen --project server python packaging/smoke.py --products packaging/out/macos-arm64/products
```

其他平台换成对应的结果目录。Linux 检查在无桌面环境下需要加 `PYSTRAY_BACKEND=xorg xvfb-run -a`。**Windows 的安装检查会安装、重装和卸载程序，只能在临时虚拟机或 CI 中运行**，避免影响已有安装。

发布前，还需手动试一下授权、鼠标键盘控制、重启和长时间使用。

## 发布新版本

1. 提交并推送代码，创建并推送版本 tag，例如 `v1.2.3` 或 `v1.2.3-rc.1`。tag 对应的代码必须包含这些打包脚本。
2. 打开 GitHub Actions，手动运行 **Release**，填写 tag、标题和说明。默认标记为预发布，正式发布时取消勾选。
3. 等待各平台构建和检查完成，流程会自动上传并发布。仅推送 tag 不会发布。

所有安装包都来自同一次指定的代码提交，发布时会附带文件清单和 SHA-256 校验文件。构建或检查失败就停止；上传失败会留下草稿，重试前需处理该草稿。已有版本不会自动覆盖。

macOS 目前只有临时签名，尚未使用 Apple 开发者证书签名或完成公证；Windows 也未做正式代码签名。首次使用的打开方式见[安装说明](../docs/README_ZH.md)。日志保存在 `~/.remote-mouse/logs`，卸载时会保留。

## English quick guide

- Install **Node.js 22, uv and Python 3.13**. Windows also needs Inno Setup 6.4+ (6.x) and x64 Python; Linux builds target Ubuntu 22.04 x64/X11 with the dependencies listed above.
- Run the build command above from the repository root. It builds for the current OS and CPU, replacing that target's previous output. Packages are in `packaging/out/<platform>-<architecture>/products/`.
- Add `--version 1.2.3` to set a version without publishing. Run the test and smoke-check commands above; use the matching products directory. Linux headless checks need `PYSTRAY_BACKEND=xorg xvfb-run -a`. **Windows installer checks must run in a disposable VM or CI**, as they install and uninstall the app.
- Push your code and a version tag, then manually run **Release** in GitHub Actions. Prerelease is enabled by default. All platforms build the same commit; failed checks stop publication. Failed uploads leave a draft to handle before retrying. Existing releases are not overwritten.
- Builds are not formally signed or notarized. See [installation instructions](../README.md). Test permissions, real input and long-running use manually before release.
