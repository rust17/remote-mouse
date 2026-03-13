use std::path::Path;
use tray_icon::{
    menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem},
    Icon, TrayIcon, TrayIconBuilder,
};

pub struct SystemTray {
    _tray: TrayIcon,
}

impl SystemTray {
    pub fn new() -> Self {
        let menu = Menu::new();
        
        // 菜单项
        let title_item = MenuItem::with_id("title", "Remote Mouse", false, None);
        let status_item = MenuItem::with_id("status", "Status: Running", false, None);
        let quit_item = MenuItem::with_id("quit", "Quit", true, None);

        let _ = menu.append_items(&[
            &title_item,
            &PredefinedMenuItem::separator(),
            &status_item,
            &PredefinedMenuItem::separator(),
            &quit_item,
        ]);

        // 加载图标
        let icon = load_icon(Path::new("assets/tray_icon.png"));

        let tray = TrayIconBuilder::new()
            .with_menu(Box::new(menu))
            .with_tooltip("Remote Mouse Server")
            .with_icon(icon)
            .build()
            .unwrap();

        Self { _tray: tray }
    }

    pub fn handle_events(&self) -> bool {
        // 检查菜单事件，如果点击了退出则返回 false
        if let Ok(event) = MenuEvent::receiver().try_recv() {
            if event.id == "quit" {
                return false;
            }
        }
        true
    }
}

fn load_icon(path: &Path) -> Icon {
    let (icon_rgba, icon_width, icon_height) = {
        let image = image::open(path)
            .expect("Failed to open tray icon")
            .into_rgba8();
        let (width, height) = image.dimensions();
        let rgba = image.into_raw();
        (rgba, width, height)
    };
    Icon::from_rgba(icon_rgba, icon_width, icon_height).expect("Failed to create icon")
}
