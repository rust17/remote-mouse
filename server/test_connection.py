import socket
import json
import time
import sys

def test_move():
    HOST = '127.0.0.1'
    PORT = 9998

    print(f"Connecting to {HOST}:{PORT}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print("Connected!")
            
            # Send move command
            print("Sending move command (dx=100, dy=100)...")
            cmd = json.dumps({"type": "move", "dx": 100, "dy": 100}) + "\n"
            s.sendall(cmd.encode('utf-8'))
            
            time.sleep(1)
            
            print("Sending move command (dx=-100, dy=-100)...")
            cmd = json.dumps({"type": "move", "dx": -100, "dy": -100}) + "\n"
            s.sendall(cmd.encode('utf-8'))
            
            print("Test finished. Did the mouse move?")
    except ConnectionRefusedError:
        print("Connection refused. Is the server running?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_move()
