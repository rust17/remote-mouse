# Remote Mouse

## 1. 项目概览
Remote Mouse 是一款轻量级、低延迟的远程控制工具，可将移动设备（iOS/Android）通过浏览器（PWA）变为电脑的无线触控板和键盘。支持 Windows, macOS, 和 Linux。

## 2. 架构概览

项目采用 **Client-Server** 架构，手机端通过浏览器或 PWA 连接电脑端服务。

- **服务端**: Python / FastAPI 提供 Web 服务和系统控制。`ServiceManager` 管理服务与 mDNS，`TrayIcon` 提供托盘 UI；输入与音量操作分别在独立工作线程中执行。
- **客户端**: TypeScript / Vite 提供电脑和 TV 两种模式，共用触控板、鼠标按键、滚动及键盘输入，按场景呈现媒体控制。
- **通信**: WebSocket 发送二进制控制指令，服务端通过 JSON 返回媒体能力、执行结果和状态。

## 3. 目录地图
```text
.
├── .github/workflows/      # 多平台构建、测试与发布流程
├── server/                 # Python 服务端，依赖由 pyproject.toml 与 uv.lock 管理
│   └── src/
│       ├── server/
│       │   ├── assets/     # 托盘图标资源
│       │   ├── core/       # 二进制协议、指标监控
│       │   ├── services/
│       │   │   ├── web.py      # HTTP/WebSocket 与静态文件托管
│       │   │   ├── manager.py  # 服务生命周期管理
│       │   │   ├── mdns.py     # 局域网服务发现
│       │   │   ├── media.py    # 媒体指令、串行输入/音量工作线程、拖拽归属
│       │   │   ├── audio.py    # macOS、Windows、Linux 系统音量适配
│       │   │   └── mouse.py    # 跨平台双击与 macOS 原生事件处理
│       │   ├── ui/         # 系统托盘 UI
│       │   ├── config.py   # 配置管理
│       │   └── main.py     # 运行入口
│       └── tests/          # 服务端测试
├── web-client/             # TypeScript / Vite PWA 客户端
│   ├── src/
│   │   ├── core/           # 协议、WebSocket 传输与国际化
│   │   ├── input/          # 触控板、滚动条与键盘输入
│   │   ├── lang/           # 中英文文案
│   │   ├── ui/             # 电脑/TV 模式、媒体控制、音量提示、设置、状态与震动
│   │   ├── main.ts         # 页面初始化与交互协调
│   │   └── style.css       # 页面样式与主题
│   ├── public/             # PWA 图标资源
│   ├── tests/              # 客户端测试
│   ├── dist/               # 构建产物，由服务端托管，不纳入 Git
│   ├── index.html          # 页面结构
│   └── vite.config.ts      # Vite 与 PWA 配置
├── packaging/              # PyInstaller 打包、安装器、发布与冒烟验证
│   └── tests/              # 打包与发布测试
├── designs/remote-mouse-ux/ # 交互原型与设计判断
├── docs/                   # 中文说明与演示图片
└── requirement/            # 历史需求文档与待办
```

## 4. 常用快速命令
### 服务端 (server/)
- **同步依赖**: `uv sync`
- **开发运行**: `uv run python -m server.main` (可带 `--port`, `--log`，开发时建议开启 `--log` 参数以启用详细日志记录)
- **静态检查**: `uv run ruff check .`
- **代码 lint**: `uv run ruff format`
- **运行测试**: `uv run pytest`

### 客户端 (web-client/)
- **安装依赖**: `npm install`
- **开发模式**: `npm run dev`
- **构建打包**: `npm run build` (产物由 Python 服务端自动托管)
- **运行测试**: `npm run test`

## 5. Git Commit 规范
遵循 **Conventional Commits** 风格：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码格式 (不影响逻辑)
- `refactor`: 重构
- `test`: 增加测试
- `chore`: 构建过程或辅助工具的变动

示例: `feat: add real-time rate monitoring`

## 6. 约束
1. README 应该从用户的角度出发，不要添加过多技术词汇
2. 操作界面上尽量不要使用文字说明，而是通过 ui、ux 自然而然地让用户知道该怎么使用
3. PR 说明用英文，保持精简，validation 只需提供方法与结果（不需要类型检查、格式检查等）
