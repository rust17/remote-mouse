import socket
import threading
import json
import pyautogui

# 禁用 PyAutoGUI 的故障保险
pyautogui.FAILSAFE = False
# 关键优化：移除每个指令后的默认暂停（默认是0.1秒），极大提升移动流畅度
pyautogui.PAUSE = 0

UDP_PORT = 9999
TCP_PORT = 9998

def get_ip():
    """获取本机局域网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不需要真的连接
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def udp_discovery_server():
    """UDP 发现服务：响应手机端的广播扫描"""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('', UDP_PORT))
        print(f"[UDP] 发现服务已启动，监听端口 {UDP_PORT}...")
        while True:
            data, addr = s.recvfrom(1024)
            if data.decode('utf-8') == "SCAN_REMOTE_MOUSE":
                print(f"[UDP] 收到来自 {addr} 的扫描请求")
                response = {
                    "hostname": socket.gethostname(),
                    "ip": get_ip(),
                    "port": TCP_PORT
                }
                s.sendto(json.dumps(response).encode('utf-8'), addr)

def handle_tcp_client(conn, addr):
    """处理单个 TCP 客户端连接"""
    print(f"[TCP] 已连接到手机: {addr}")

    # 优化：禁用 Nagle 算法，降低延迟
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    with conn:
        buffer = ""
        while True:
            try:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break

                buffer += data
                # 处理粘包：假设每个指令以换行符结束
                if "\n" in buffer:
                    lines = buffer.split("\n")
                    for line in lines[:-1]:
                        if not line: continue
                        try:
                            cmd = json.loads(line)
                            execute_command(cmd)
                        except Exception as e:
                            print(f"解析指令出错: {e}")
                    buffer = lines[-1]
            except ConnectionResetError:
                break
            except Exception as e:
                print(f"连接异常: {e}")
                break

    print(f"[TCP] 手机断开连接: {addr}")

def execute_command(cmd):
    """根据收到的 JSON 执行具体操作"""
    action = cmd.get("type")

    if action == "move":
        dx = int(cmd.get("dx", 0))
        dy = int(cmd.get("dy", 0))
        # 临时加回日志以调试
        # print(f"[Mouse] Move: ({dx}, {dy})")
        pyautogui.moveRel(dx, dy)

    elif action == "click":
        button = cmd.get("button", "left")
        # print(f"[Mouse] Click: {button}")
        pyautogui.click(button=button)

    elif action == "scroll":
        amount = cmd.get("amount", 0)
        # print(f"[Mouse] Scroll: {amount}")
        pyautogui.scroll(amount)

    elif action == "text":
        text = cmd.get("text", "")
        # print(f"[Keyboard] Type Text: '{text}'")
        pyautogui.write(text)

    elif action == "key":
        key = cmd.get("key", "")
        if key:
            # print(f"[Keyboard] Press Key: {key}")
            pyautogui.press(key)

    elif action == "keyDown":
        key = cmd.get("key", "")
        if key:
            # print(f"[Keyboard] Key Down: {key}")
            pyautogui.keyDown(key)

    elif action == "keyUp":
        key = cmd.get("key", "")
        if key:
            # print(f"[Keyboard] Key Up: {key}")
            pyautogui.keyUp(key)

def tcp_control_server():
    """TCP 指令服务：接收具体的控制指令"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', TCP_PORT))
        s.listen(1)
        print(f"[TCP] 指令服务已启动，监听端口 {TCP_PORT}...")
        while True:
            conn, addr = s.accept()
            # 为每个连接开启线程（虽然通常只有一个手机控制）
            threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    print(f"--- 远程鼠标服务端已启动 ---")
    print(f"本机 IP: {get_ip()}")

    # 启动 UDP 发现线程
    threading.Thread(target=udp_discovery_server, daemon=True).start()

    # 启动 TCP 控制服务（主线程运行）
    tcp_control_server()
