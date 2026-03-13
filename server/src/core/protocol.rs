use byteorder::{BigEndian, ReadBytesExt};
use std::io::Cursor;

#[derive(Debug, PartialEq)]
pub enum ProtocolCommand {
    Move { dx: i16, dy: i16 },
    Click { button: u8, modifier_mask: u8 },
    Scroll { sx: i16, sy: i16 },
    Drag { down: bool },
    Text(String),
    KeyAction { modifier_mask: u8, key_name: String },
}

pub fn parse_command(data: &[u8]) -> Option<ProtocolCommand> {
    if data.is_empty() {
        return None;
    }

    let opcode = data[0];
    let mut reader = Cursor::new(&data[1..]);

    match opcode {
        // OP_MOVE (0x01): [dx: i16] [dy: i16]
        0x01 => {
            if data.len() < 5 { return None; }
            let dx = reader.read_i16::<BigEndian>().ok()?;
            let dy = reader.read_i16::<BigEndian>().ok()?;
            Some(ProtocolCommand::Move { dx, dy })
        }
        // OP_CLICK (0x02): [button: u8] [modifier_mask: u8]
        0x02 => {
            if data.len() < 2 { return None; }
            let button = data[1];
            let modifier_mask = if data.len() >= 3 { data[2] } else { 0 };
            Some(ProtocolCommand::Click { button, modifier_mask })
        }
        // OP_SCROLL (0x03): [sx: i16] [sy: i16]
        0x03 => {
            if data.len() < 5 { return None; }
            let sx = reader.read_i16::<BigEndian>().ok()?;
            let sy = reader.read_i16::<BigEndian>().ok()?;
            Some(ProtocolCommand::Scroll { sx, sy })
        }
        // OP_DRAG (0x04): [state: u8 (0x01 is down)]
        0x04 => {
            if data.len() < 2 { return None; }
            let down = data[1] == 0x01;
            Some(ProtocolCommand::Drag { down })
        }
        // OP_TEXT (0x05): [UTF-8 payload]
        0x05 => {
            let text = String::from_utf8_lossy(&data[1..]).into_owned();
            Some(ProtocolCommand::Text(text))
        }
        // OP_KEY_ACTION (0x06): [modifier_mask: u8] [key_name: UTF-8]
        0x06 => {
            if data.len() < 2 { return None; }
            let modifier_mask = data[1];
            let key_name = String::from_utf8_lossy(&data[2..]).into_owned();
            Some(ProtocolCommand::KeyAction { modifier_mask, key_name })
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_move() {
        let data = vec![0x01, 0x00, 0x0A, 0xFF, 0xF6]; // Op: 1, dx: 10, dy: -10
        let cmd = parse_command(&data).unwrap();
        assert_eq!(cmd, ProtocolCommand::Move { dx: 10, dy: -10 });
    }

    #[test]
    fn test_parse_click() {
        let data = vec![0x02, 0x01, 0x08]; // Op: 2, Button: 1, Mask: 8 (Win)
        let cmd = parse_command(&data).unwrap();
        assert_eq!(cmd, ProtocolCommand::Click { button: 1, modifier_mask: 8 });
    }

    #[test]
    fn test_parse_text() {
        let text = "你好";
        let mut data = vec![0x05];
        data.extend_from_slice(text.as_bytes());
        let cmd = parse_command(&data).unwrap();
        assert_eq!(cmd, ProtocolCommand::Text(text.to_string()));
    }
}
