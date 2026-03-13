fn main() {
    // 预留后续 Windows 图标和清单配置
    #[cfg(target_os = "windows")]
    embed_resource::compile("assets/remote-mouse.rc");
}
