use enigo::{Axis, Button, Direction, Enigo, Key, Keyboard, Mouse, Settings};
use std::error::Error;
use tracing::error;

pub struct InputService {
    enigo: Enigo,
    scroll_remainder_x: f32,
    scroll_remainder_y: f32,
}

impl InputService {
    pub fn new() -> Result<Self, Box<dyn Error>> {
        let enigo = Enigo::new(&Settings::default())?;
        Ok(Self {
            enigo,
            scroll_remainder_x: 0.0,
            scroll_remainder_y: 0.0,
        })
    }

    // --- Mouse Controller ---

    pub fn mouse_move_relative(&mut self, dx: i32, dy: i32) {
        if let Err(e) = self.enigo.move_mouse(dx, dy, enigo::Coordinate::Rel) {
            error!("Mouse move failed: {:?}", e);
        }
    }

    pub fn mouse_click(&mut self, button: Button, modifiers: &[Key]) {
        // 按下修饰键
        for &m in modifiers {
            let _ = self.enigo.key(m, Direction::Press);
        }

        if let Err(e) = self.enigo.button(button, Direction::Click) {
            error!("Mouse click failed: {:?}", e);
        }

        // 释放修饰键
        for &m in modifiers.iter().rev() {
            let _ = self.enigo.key(m, Direction::Release);
        }
    }

    pub fn mouse_scroll(&mut self, dx: i32, dy: i32) {
        // 降低滚动灵敏度并保留小数部分
        let tx = dx as f32 * 0.3 + self.scroll_remainder_x;
        let ty = dy as f32 * 0.3 + self.scroll_remainder_y;

        let ix = tx.trunc();
        let iy = ty.trunc();

        self.scroll_remainder_x = tx - ix;
        self.scroll_remainder_y = ty - iy;

        // Enigo 0.3.0 使用 Axis 枚举
        if iy != 0.0 {
            // 反转方向
            if let Err(e) = self.enigo.scroll(-(iy as i32), Axis::Vertical) {
                error!("Vertical scroll failed: {:?}", e);
            }
        }
        if ix != 0.0 {
            if let Err(e) = self.enigo.scroll(ix as i32, Axis::Horizontal) {
                error!("Horizontal scroll failed: {:?}", e);
            }
        }
    }

    pub fn mouse_set_drag(&mut self, down: bool) {
        let direction = if down {
            Direction::Press
        } else {
            Direction::Release
        };
        if let Err(e) = self.enigo.button(Button::Left, direction) {
            error!("Mouse drag state change failed: {:?}", e);
        }
    }

    // --- Keyboard Controller ---

    pub fn key_click(&mut self, key: Key, modifiers: &[Key]) {
        // 按下修饰键
        for &m in modifiers {
            let _ = self.enigo.key(m, Direction::Press);
        }

        // 点击目标键
        if let Err(e) = self.enigo.key(key, Direction::Click) {
            error!("Key click failed: {:?}", e);
        }

        // 释放修饰键 (逆序)
        for &m in modifiers.iter().rev() {
            let _ = self.enigo.key(m, Direction::Release);
        }
    }

    pub fn type_text(&mut self, text: &str) {
        if let Err(e) = self.enigo.text(text) {
            error!("Text input failed: {:?}", e);
        }
    }

    /// 将字符串键名映射为 Enigo 的 Key 枚举
    pub fn map_key_name(name: &str) -> Option<Key> {
        match name.to_lowercase().as_str() {
            "enter" | "return" => Some(Key::Return),
            "backspace" => Some(Key::Backspace),
            "escape" | "esc" => Some(Key::Escape),
            "tab" => Some(Key::Tab),
            "space" => Some(Key::Space),
            "up" => Some(Key::UpArrow),
            "down" => Some(Key::DownArrow),
            "left" => Some(Key::LeftArrow),
            "right" => Some(Key::RightArrow),
            "home" => Some(Key::Home),
            "end" => Some(Key::End),
            "pageup" => Some(Key::PageUp),
            "pagedown" => Some(Key::PageDown),
            "delete" => Some(Key::Delete),
            "f1" => Some(Key::F1),
            "f2" => Some(Key::F2),
            "f3" => Some(Key::F3),
            "f4" => Some(Key::F4),
            "f5" => Some(Key::F5),
            "f6" => Some(Key::F6),
            "f7" => Some(Key::F7),
            "f8" => Some(Key::F8),
            "f9" => Some(Key::F9),
            "f10" => Some(Key::F10),
            "f11" => Some(Key::F11),
            "f12" => Some(Key::F12),
            // 修饰键映射
            "ctrl" | "control" => Some(Key::Control),
            "shift" => Some(Key::Shift),
            "alt" | "option" => Some(Key::Alt),
            "win" | "command" | "meta" => {
                #[cfg(target_os = "macos")]
                {
                    Some(Key::Meta)
                }
                #[cfg(not(target_os = "macos"))]
                {
                    Some(Key::Meta)
                } // Enigo 会根据平台处理 Meta
            }
            _ => None,
        }
    }

    /// 解析前端传来的位掩码修饰键
    /// Bit 0: Ctrl, Bit 1: Shift, Bit 2: Alt, Bit 3: Win/Cmd
    pub fn parse_modifiers(mask: u8) -> Vec<Key> {
        let mut modifiers = Vec::new();
        if mask & 1 != 0 {
            modifiers.push(Key::Control);
        }
        if mask & 2 != 0 {
            modifiers.push(Key::Shift);
        }
        if mask & 4 != 0 {
            modifiers.push(Key::Alt);
        }
        if mask & 8 != 0 {
            modifiers.push(Key::Meta);
        }
        modifiers
    }
}
