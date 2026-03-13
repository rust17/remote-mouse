use std::thread;
use tokio::sync::mpsc;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod core;
mod services;
mod ui;

use crate::core::protocol::ProtocolCommand;
use crate::services::{input::InputService, mdns::MDNSResponder, web::WebService};
use crate::ui::SystemTray;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. 初始化日志
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new("info"))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting Remote Mouse Server...");

    // 2. 创建通信通道 (Web -> Input Worker)
    let (tx, mut rx) = mpsc::unbounded_channel::<ProtocolCommand>();

    // 3. 启动后台处理线程 (Tokio Runtime)
    thread::spawn(move || {
        let runtime = tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap();

        runtime.block_on(async {
            // 启动 mDNS
            let mdns = MDNSResponder::new(9997);
            if let Err(e) = mdns.start() {
                error!("mDNS failed: {}", e);
            }

            // 启动 Web 服务
            let web = WebService::new(9997, tx);
            if let Err(e) = web.start().await {
                error!("Web service failed: {}", e);
            }
        });
    });

    // 4. 在后台线程运行输入控制 Worker (处理同步 Enigo 调用)
    thread::spawn(move || {
        let mut input_service = match InputService::new() {
            Ok(service) => service,
            Err(e) => {
                error!("Failed to initialize InputService: {}", e);
                return;
            }
        };

        info!("Input worker started");
        while let Some(cmd) = rx.blocking_recv() {
            match cmd {
                ProtocolCommand::Move { dx, dy } => {
                    input_service.mouse_move_relative(dx as i32, dy as i32);
                }
                ProtocolCommand::Click {
                    button,
                    modifier_mask,
                } => {
                    use enigo::Button;
                    let btn = if button == 0x01 {
                        Button::Left
                    } else {
                        Button::Right
                    };
                    let mods = InputService::parse_modifiers(modifier_mask);
                    // 点击
                    input_service.mouse_click(btn, &mods);
                }
                ProtocolCommand::Scroll { sx, sy } => {
                    input_service.mouse_scroll(sx as i32, sy as i32);
                }
                ProtocolCommand::Drag { down } => {
                    input_service.mouse_set_drag(down);
                }
                ProtocolCommand::Text(text) => {
                    input_service.type_text(&text);
                }
                ProtocolCommand::KeyAction {
                    modifier_mask,
                    key_name,
                } => {
                    if let Some(key) = InputService::map_key_name(&key_name) {
                        let mods = InputService::parse_modifiers(modifier_mask);
                        input_service.key_click(key, &mods);
                    }
                }
            }
        }
    });

    // 5. 主线程：运行系统托盘 (阻塞)
    let event_loop = tao::event_loop::EventLoop::new();
    let tray = SystemTray::new();

    event_loop.run(move |event, _el, control_flow| {
        if let tao::event::Event::WindowEvent { .. } = event {
            // 这里可以处理窗口事件
        }
        
        // 持续轮询托盘事件
        if !tray.handle_events() {
            info!("Shutting down...");
            *control_flow = tao::event_loop::ControlFlow::Exit;
            std::process::exit(0);
        }
    });
}

