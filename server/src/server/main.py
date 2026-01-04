import socket
import threading
import json
import pyautogui
import sys
import os
from PIL import Image, ImageDraw
import pystray

# 禁用 PyAutoGUI 的故障保险（防止鼠标移动到角落触发退出）
pyautogui.FAILSAFE = False
# 关键优化：移除每个指令后的默认暂停（默认是0.1秒），极大提升移动流畅度
pyautogui.PAUSE = 0

UDP_PORT = 9999
TCP_PORT = 9998
server_running = True


def get_ip():
    """获取本机局域网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不需要真的连接
        s.connect(("8.8.8.8", 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        s.close()
    return IP


def create_image():
    """创建一个简单的图标（蓝色方块）"""
    width = 64
    height = 64
    color1 = "blue"
    color2 = "white"

    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)

    return image


def on_quit(icon, item):
    """点击托盘退出菜单时的回调"""
    global server_running
    server_running = False
    icon.stop()
    print("正在退出服务端...")
    # 使用 os._exit 强制退出，确保后台线程不会阻塞进程关闭
    os._exit(0)


def udp_discovery_server():
    """UDP 发现服务：响应手机端的广播扫描"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(("", UDP_PORT))
            print(f"[UDP] 发现服务已启动，监听端口 {UDP_PORT}...")
            # 设置超时以便循环能检查 server_running 状态
            s.settimeout(1.0)
            while server_running:
                try:
                    data, addr = s.recvfrom(1024)
                    if data.decode("utf-8") == "SCAN_REMOTE_MOUSE":
                        response = {
                            "hostname": socket.gethostname(),
                            "ip": get_ip(),
                            "port": TCP_PORT,
                        }
                        s.sendto(json.dumps(response).encode("utf-8"), addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[UDP] 错误: {e}")
    except Exception as e:
        print(f"[UDP] 绑定失败: {e}")


def handle_tcp_client(conn, addr):
    """处理单个 TCP 客户端连接"""
    print(f"[TCP] 已连接到手机: {addr}")

    # 禁用 Nagle 算法，降低实时操作的延迟
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    with conn:
        buffer = ""
        while server_running:
            try:
                data = conn.recv(1024).decode("utf-8")
                if not data:
                    break

                buffer += data
                # 处理粘包：每个指令以换行符结束
                if "\n" in buffer:
                    lines = buffer.split("\n")

                    # 1. 先解析所有完整指令
                    commands = []
                    for line in lines[:-1]:
                        if not line:
                            continue
                        try:
                            commands.append(json.loads(line))
                        except Exception as e:
                            print(f"解析指令出错: {e}")

                    # 2. 优化：合并连续的移动指令，防止积压导致光标延迟/滑冰
                    pending_dx = 0
                    pending_dy = 0

                    for cmd in commands:
                        if cmd.get("type") == "move":
                            pending_dx += int(cmd.get("dx", 0))
                            pending_dy += int(cmd.get("dy", 0))
                        else:
                            # 遇到非移动指令，先执行累积的移动
                            if pending_dx != 0 or pending_dy != 0:
                                execute_command(
                                    {"type": "move", "dx": pending_dx, "dy": pending_dy}
                                )
                                pending_dx = 0
                                pending_dy = 0
                            # 执行当前指令
                            execute_command(cmd)

                    # 循环结束后，执行剩余的移动
                    if pending_dx != 0 or pending_dy != 0:
                        execute_command({"type": "move", "dx": pending_dx, "dy": pending_dy})

                    buffer = lines[-1]
            except ConnectionResetError:
                break
            except Exception as e:
                # 打印异常有助于调试连接中断
                print(f"[TCP] 连接异常: {e}")
                break

    print(f"[TCP] 手机断开连接: {addr}")


def execute_command(cmd):
    """执行从客户端收到的指令"""
    try:
        action = cmd.get("type")

        # 调试日志：打印接收到的指令
        # if action != "move":  # 过滤移动指令以防刷屏
        #     print(f"[DEBUG] 收到指令: {cmd}")
        # else:
        #     print(f"[DEBUG] 移动: dx={cmd.get('dx')}, dy={cmd.get('dy')}")

        if action == "move":
            dx = int(cmd.get("dx", 0))
            dy = int(cmd.get("dy", 0))
            pyautogui.moveRel(dx, dy)

        elif action == "click":
            button = cmd.get("button", "left")
            pyautogui.click(button=button)

        elif action == "drag_start":
            # 模拟左键按下不放
            pyautogui.mouseDown(button="left")

        elif action == "drag_end":
            # 释放左键
            pyautogui.mouseUp(button="left")

        elif action == "scroll":
            amount = int(cmd.get("amount", 0))
            pyautogui.scroll(amount)

        elif action == "text":
            text = cmd.get("text", "")
            pyautogui.write(text)

        elif action == "key":
            key = cmd.get("key", "")
            if key:
                pyautogui.press(key)

        elif action == "keyDown":
            key = cmd.get("key", "")
            if key:
                pyautogui.keyDown(key)

        elif action == "keyUp":
            key = cmd.get("key", "")
            if key:
                pyautogui.keyUp(key)

    except pyautogui.FailSafeException:
        print("警告: 触发了 PyAutoGUI 安全限制")
    except Exception as e:
        print(f"执行指令 '{cmd}' 时出错: {e}")


def tcp_control_server():
    """TCP 指令服务：监听并接收连接"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("", TCP_PORT))
            s.listen(1)
            s.settimeout(1.0)
            print(f"[TCP] 指令服务已启动，监听端口 {TCP_PORT}...")
            while server_running:
                try:
                    conn, addr = s.accept()
                    # 为每个新连接开启线程
                    threading.Thread(
                        target=handle_tcp_client, args=(conn, addr), daemon=True
                    ).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[TCP] 监听出错: {e}")
    except Exception as e:
        print(f"[TCP] 绑定失败: {e}")


def start_background_services():
    """启动所有网络监听服务线程"""
    print(f"--- Remote Mouse 服务端 V2 ---")
    print(f"本机 IP 地址: {get_ip()}")

    # UDP 发现服务线程
    threading.Thread(target=udp_discovery_server, daemon=True).start()

    # TCP 控制服务线程
    threading.Thread(target=tcp_control_server, daemon=True).start()


if __name__ == "__main__":
    # 1. 启动网络后台服务
    start_background_services()

    # 2. 启动系统托盘图标（主线程运行 GUI 事件循环）
    ip_addr = get_ip()
    menu = pystray.Menu(
        pystray.MenuItem(f"IP: {ip_addr}", lambda: None, enabled=False),
        pystray.MenuItem("Exit", on_quit),
    )

    icon = pystray.Icon("RemoteMouse", create_image(), "Remote Mouse Server", menu)

    print("程序已最小化到系统托盘运行。")
    icon.run()
