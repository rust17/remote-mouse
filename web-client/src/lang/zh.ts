export const zh = {
    status: {
        connecting: '正在连接...',
        connected: '已连接',
        disconnected: '连接断开',
        error: '连接错误',
        failed: '连接失败',
    },
    settings: {
        title: '设置',
        mouse_sensitivity: '鼠标灵敏度',
        scroll_sensitivity: '滚动灵敏度',
        input_mode: '输入方式',
        light_mode: '亮色模式',
        scroll_bar_right: '滚动条居右',
        rate_monitor: '速率监控器',
        language: '语言',
    },
    ui: {
        close: '关闭',
    },
    mode: { label: '操作模式', computer: '电脑模式', tv: 'TV 模式' },
    mouse: { touchpad: '触控板', scroll: '单指滚动' },
    input: {
        open: '展开键盘', close: '收起键盘', realtime: '实时输入', draft: '编辑后发送',
        draft_text: '待发送文字', send: '发送文字', not_sent: '连接断开，草稿未发送',
        function_keys: '电脑功能键', select_all: '全选', enter: '确认（Enter）',
        backspace: '退格', tab: 'Tab', up: '上', down: '下', left: '左', right: '右',
    },
    media: {
        audio_dependency: '缺少系统音量依赖（Windows: pycaw；Linux: pactl）', audio_permission: '缺少系统音量访问权限', audio_no_device: '没有默认音频输出设备',
        detecting: '正在探测媒体能力…', system_volume: '系统音量',
        hint: '先让播放器获得焦点；全屏前把电脑鼠标移到视频画面',
        sending: '正在执行…', issued: '输入已发送，播放器状态未知',
        verified: '系统音量 / 静音状态已验证', failed: '执行失败，请查看不可用原因',
        timeout: '未收到回执，执行结果未知；未自动重发',
        input_permission: '电脑端缺少辅助功能权限', input_unsupported: '当前桌面不支持模拟输入',
        drag_busy: '拖拽期间不可双击', audio_unavailable: '系统音量不可用：请检查依赖、权限和默认输出设备',
        execution_failed: '操作失败或系统未确认变更',
        label: 'TV 媒体控制', unavailable: '未收到媒体能力，按钮暂不可用',
        rewind: '快退', play_pause: '播放 / 暂停', forward: '快进',
        volume_down: '降低音量', mute: '静音切换', volume_up: '提高音量', fullscreen: '电脑播放器全屏',
    },
};

export type TranslationKeys = typeof zh;
