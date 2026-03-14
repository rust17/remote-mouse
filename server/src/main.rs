#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::thread;
use tokio::sync::mpsc;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod core;
mod services;

use crate::core::protocol::ProtocolCommand;
use crate::services::{input::InputService, mdns::MDNSResponder, web::WebService};

use tauri::{
    menu::{CheckMenuItem, Menu, MenuItem, PredefinedMenuItem},
    tray::TrayIconBuilder,
};
use tauri_plugin_autostart::ManagerExt as _;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_updater::UpdaterExt as _;

const DEFAULT_PORT: u16 = 9997;

fn main() {
    // 1. 初始化日志
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new("info"))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting Remote Mouse Tauri Server...");

    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--hidden"]),
        ))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            let ip = local_ip_address::local_ip()
                .map(|ip| ip.to_string())
                .unwrap_or_else(|_| "Unknown".to_string());
            let address = format!("Address: http://{}:{}", ip, DEFAULT_PORT);

            // 设置系统托盘菜单
            let title_i = MenuItem::with_id(app, "title", "Remote Mouse", false, None::<&str>)?;
            let addr_i = MenuItem::with_id(app, "address", &address, false, None::<&str>)?;

            // 开机自启
            let is_autostart_enabled = app.autolaunch().is_enabled().unwrap_or(false);
            let autostart_i = CheckMenuItem::with_id(
                app,
                "toggle_autostart",
                "Auto-start",
                true,
                is_autostart_enabled,
                None::<&str>,
            )?;

            // 检查更新
            let update_i = MenuItem::with_id(app, "check_update", "Check for updates", true, None::<&str>)?;

            let quit_i = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let separator = PredefinedMenuItem::separator(app)?;

            let menu = Menu::with_items(
                app,
                &[
                    &title_i,
                    &separator,
                    &addr_i,
                    &separator,
                    &autostart_i,
                    &update_i,
                    &separator,
                    &quit_i,
                ],
            )?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "toggle_autostart" => {
                        let manager = app.autolaunch();
                        if manager.is_enabled().unwrap_or(false) {
                            let _ = manager.disable();
                            info!("Autostart disabled");
                        } else {
                            let _ = manager.enable();
                            info!("Autostart enabled");
                        }
                    }
                    "check_update" => {
                        let handle = app.clone();
                        tauri::async_runtime::spawn(async move {
                            info!("Checking for updates...");
                            match handle.updater() {
                                Ok(updater) => match updater.check().await {
                                    Ok(Some(update)) => {
                                        info!("Found update: {}", update.version);
                                        let message = format!("Found new version {}, would you like to update and restart now?", update.version);
                                        let answer = handle
                                            .dialog()
                                            .message(message)
                                            .title("Check for update")
                                            .kind(MessageDialogKind::Info)
                                            .buttons(MessageDialogButtons::YesNo)
                                            .blocking_show();

                                        if answer {
                                            info!("User confirmed update. Downloading...");
                                            if let Err(e) = update.download_and_install(|_, _| {}, || {}).await {
                                                error!("Failed to install update: {}", e);
                                            } else {
                                                info!("Update installed. Restarting...");
                                                handle.restart();
                                            }
                                        }
                                    }
                                    Ok(None) => {
                                        info!("No update found");
                                        let _ = handle
                                            .dialog()
                                            .message("You are on the latest version.")
                                            .title("Check for update")
                                            .kind(MessageDialogKind::Info)
                                            .buttons(MessageDialogButtons::Ok)
                                            .blocking_show();
                                    }
                                    Err(e) => {
                                        error!("Failed to check for updates: {}", e);
                                    }
                                },
                                Err(e) => {
                                    error!("Failed to get updater: {}", e);
                                }
                            }
                        });
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

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
                    let mut mdns = MDNSResponder::new(DEFAULT_PORT);
                    if let Err(e) = mdns.start() {
                        error!("mDNS failed: {}", e);
                    }

                    // 启动 Web 服务
                    let web = WebService::new(DEFAULT_PORT, tx);
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

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
