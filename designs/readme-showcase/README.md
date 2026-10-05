# README 宣传素材

以当前正式客户端为来源，更新中英文 README 的主视觉、界面图和动图。沿用客户端的深色背景、电蓝重点色与现有图标；宣传素材保存在 `docs/images/`，制作源文件保存在本目录。

## 设计判断

- 首屏先交代产品价值、适用设备与下载入口；主视觉并列展示电脑模式和浅色 TV 模式。
- 12 秒循环动图按触控板、文字发送、TV 控制三个场景展开。手机界面是正式客户端截图；触点和电脑响应为交互示意，图中及 README 均有说明。
- 安装、手势和排查说明完整保留，使用 GitHub 支持的折叠区，方便访客按需阅读。
- 中英文素材分别配文；PNG 保持界面与文字清晰，GIF 使用差分调色板减小体积。

## 来源与范围

- 界面：`web-client/index.html`、`web-client/src/style.css`、`web-client/src/main.ts` 及输入、媒体、设置模块。
- 图标：`web-client/public/pwa-192x192.png`，复制为本目录的 `icon.png`。
- 功能说明：`CHANGELOG.md`、`packaging/README.md`、`designs/remote-mouse-ux/设计判断.md`，并与正式代码核对。原型中的未实现行为不用于宣传。
- `capture.mjs` 使用仅用于截图的 WebSocket 数据，让客户端显示已连接和可用媒体按钮；不会操作本机鼠标、键盘或音量。截图不包含手机系统软键盘。

## 预览与重新生成

需要 Node.js、Playwright Chromium 和 FFmpeg。Playwright 可安装在仓库外的工具目录，通过 `NODE_PATH` 指向该目录的 `node_modules`，不用修改客户端依赖。首次安装后运行 `playwright install chromium`。如需指定已有 Chromium，可设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`。

在仓库根目录执行，前两个服务分别保持运行：

```bash
npm --prefix web-client run dev -- --host 127.0.0.1 --port 5173 --strictPort
python3 -m http.server 4311 --bind 127.0.0.1 --directory designs
node designs/readme-showcase/capture.mjs
node designs/readme-showcase/export.mjs
```

打开 `http://127.0.0.1:4311/readme-showcase/showcase.html` 查看主视觉、动态演示和界面图，支持中英文切换与播放暂停。也可用 `?kind=demo&lang=zh` 直接进入对应视图。

`REMOTE_MOUSE_CLIENT_URL` 和 `REMOTE_MOUSE_SHOWCASE_URL` 可覆盖默认地址。导出文件进入 `docs/images/`；中间帧保存在已忽略的 `frames/`。重新生成时会覆盖同名素材。

## 验证记录

- 截取 14 个正式客户端状态，无浏览器运行错误。
- 检查主视觉、界面图与动图各场景，以及 390 px 窄屏预览。
- 检查中英文 README 的本地文件引用、展开内容与图片加载。
- 仅修改文档和展示素材；无需运行服务端或发送真实电脑控制指令。
