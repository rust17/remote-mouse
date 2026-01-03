import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  runApp(const RemoteMouseApp());
}

class RemoteMouseApp extends StatelessWidget {
  const RemoteMouseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Remote Mouse',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const DiscoveryPage(),
    );
  }
}

/// 页面 1: 设备发现与扫描
class DiscoveryPage extends StatefulWidget {
  const DiscoveryPage({super.key});

  @override
  State<DiscoveryPage> createState() => _DiscoveryPageState();
}

class _DiscoveryPageState extends State<DiscoveryPage> {
  List<Map<String, dynamic>> _devices = [];
  bool _isScanning = false;
  RawDatagramSocket? _udpSocket;

  @override
  void initState() {
    super.initState();
    _startScan();
  }

  @override
  void dispose() {
    _udpSocket?.close();
    super.dispose();
  }

  Future<void> _startScan() async {
    if (_isScanning) return;

    setState(() {
      _isScanning = true;
      _devices.clear();
    });

    try {
      // 1. 获取本机所有 IPv4 网络接口
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLoopback: false,
      );

      String? localIp;
      String? broadcastIp;

      // 寻找合适的 Wi-Fi 网卡地址
      for (var interface in interfaces) {
        for (var addr in interface.addresses) {
          if (!addr.address.startsWith('169.254')) {
            localIp = addr.address;
            final parts = localIp.split('.');
            if (parts.length == 4) {
              broadcastIp = "${parts[0]}.${parts[1]}.${parts[2]}.255";
              break;
            }
          }
        }
        if (localIp != null) break;
      }

      if (localIp == null || broadcastIp == null) {
        print("未找到合适的网络接口");
        return;
      }

      // 2. 绑定到具体的本地 IP (关键：解决 iOS No route to host 报错)
      _udpSocket = await RawDatagramSocket.bind(localIp, 0);
      _udpSocket?.broadcastEnabled = true;

      _udpSocket?.listen((RawSocketEvent event) {
        if (event == RawSocketEvent.read) {
          final datagram = _udpSocket?.receive();
          if (datagram != null) {
            try {
              final message = utf8.decode(datagram.data);
              final data = jsonDecode(message);
              if (!_devices.any((d) => d['ip'] == data['ip'])) {
                setState(() {
                  _devices.add(data);
                });
              }
            } catch (e) {
              print("UDP 解析错误: $e");
            }
          }
        }
      });

      // 3. 发送广播包到计算出的子网广播地址
      final data = utf8.encode("SCAN_REMOTE_MOUSE");
      for (int i = 0; i < 3; i++) {
        _udpSocket?.send(data, InternetAddress(broadcastIp), 9999);
        await Future.delayed(const Duration(milliseconds: 500));
      }
    } catch (e) {
      print("扫描出错: $e");
    } finally {
      if (mounted) {
        setState(() {
          _isScanning = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('选择设备'),
        actions: [
          IconButton(
            icon: _isScanning
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.refresh),
            onPressed: _startScan,
          )
        ],
      ),
      body: _devices.isEmpty
          ? Center(
              child: _isScanning
                  ? const Text("正在扫描局域网设备...")
                  : const Text("未发现设备，请确保电脑端服务已开启"),
            )
          : ListView.builder(
              itemCount: _devices.length,
              itemBuilder: (context, index) {
                final device = _devices[index];
                return ListTile(
                  leading: const Icon(Icons.computer),
                  title: Text(device['hostname'] ?? 'Unknown'),
                  subtitle: Text(device['ip'] ?? ''),
                  trailing: const Icon(Icons.arrow_forward_ios),
                  onTap: () {
                    // 停止扫描并跳转
                    _udpSocket?.close();
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => ControlPage(
                          serverIp: device['ip'],
                          serverPort: device['port'] ?? 9998,
                        ),
                      ),
                    );
                  },
                );
              },
            ),
    );
  }
}

/// 页面 2: 鼠标控制面板
class ControlPage extends StatefulWidget {
  final String serverIp;
  final int serverPort;

  const ControlPage(
      {super.key, required this.serverIp, required this.serverPort});

  @override
  State<ControlPage> createState() => _ControlPageState();
}

class _ControlPageState extends State<ControlPage> {
  Socket? _socket;
  bool _isConnected = false;
  String _statusMessage = "正在连接...";

  // 触摸板相关状态
  double _sensitivity = 2.0; // 灵敏度

  // 键盘相关
  final TextEditingController _textController = TextEditingController();
  final FocusNode _textFocusNode = FocusNode();
  String _lastText = "";

  // 修饰键状态
  final Map<String, bool> _modifierKeys = {
    "ctrl": false,
    "alt": false,
    "shift": false,
    "command": false, // win/cmd
  };

  @override
  void initState() {
    super.initState();
    _connectToServer();
  }

  @override
  void dispose() {
    _socket?.destroy();
    _textController.dispose();
    _textFocusNode.dispose();
    super.dispose();
  }

  Future<void> _connectToServer() async {
    try {
      _socket = await Socket.connect(widget.serverIp, widget.serverPort);
      setState(() {
        _isConnected = true;
        _statusMessage = "已连接";
      });

      _socket!.listen(
        (data) {},
        onError: (error) {
          _handleDisconnect("连接错误: $error");
        },
        onDone: () {
          _handleDisconnect("连接断开");
        },
      );
    } catch (e) {
      _handleDisconnect("连接失败: $e");
    }
  }

  void _handleDisconnect(String msg) {
    if (mounted) {
      setState(() {
        _isConnected = false;
        _statusMessage = msg;
        // 重置所有修饰键状态
        _modifierKeys.updateAll((key, value) => false);
      });
    }
  }

  void _sendCommand(Map<String, dynamic> cmd) {
    if (_socket != null && _isConnected) {
      try {
        _socket!.write(jsonEncode(cmd) + "\n");
      } catch (e) {
        print("发送失败: $e");
      }
    }
  }

  void _handleTextChange(String newText) {
    if (newText.length > _lastText.length) {
      // 有新字符输入
      String diff = newText.substring(_lastText.length);
      _sendCommand({"type": "text", "text": diff});
    } else if (newText.length < _lastText.length) {
      // 删除了字符，发送退格键
      int deleteCount = _lastText.length - newText.length;
      for (int i = 0; i < deleteCount; i++) {
        _sendCommand({"type": "key", "key": "backspace"});
      }
    }
    _lastText = newText;
  }

  void _toggleModifierKey(String key) {
    bool isActive = _modifierKeys[key] ?? false;
    setState(() {
      _modifierKeys[key] = !isActive;
    });

    // 发送 keyDown 或 keyUp
    if (!isActive) {
      _sendCommand({"type": "keyDown", "key": key});
    } else {
      _sendCommand({"type": "keyUp", "key": key});
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isConnected ? '已连接: ${widget.serverIp}' : '未连接'),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(20),
          child: Text(
            _statusMessage,
            style: TextStyle(
                color: _isConnected ? Colors.green : Colors.red, fontSize: 12),
          ),
        ),
      ),
      body: Column(
        children: [
          // 隐形输入框，用于唤起键盘并监听输入
          Offstage(
            offstage: true,
            child: TextField(
              controller: _textController,
              focusNode: _textFocusNode,
              autocorrect: false,
              enableSuggestions: false,
              keyboardType: TextInputType.visiblePassword, // 避免联想
              onChanged: _handleTextChange,
            ),
          ),
          // 上半部分：触摸板区域
          Expanded(
            flex: 10,
            child: Container(
              width: double.infinity,
              color: Colors.grey[200],
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onPanUpdate: (details) {
                  int dx = (details.delta.dx * _sensitivity).toInt();
                  int dy = (details.delta.dy * _sensitivity).toInt();
                  // 只有当有实际位移时才发送，减少空包
                  if (dx != 0 || dy != 0) {
                    _sendCommand({"type": "move","dx": dx, "dy": dy});
                  }
                },
                onTap: () {
                  _sendCommand({"type": "click", "button": "left"});
                },
              ),
            ),
          ),
          const Divider(height: 1),
          // 下半部分：功能键
          Expanded(
            flex: 1,
            child: Row(
              children: [
                // 左键
                Expanded(
                  child: InkWell(
                    onTap: () =>
                        _sendCommand({"type": "click", "button": "left"}),
                    child: Container(
                      color: Colors.blue[50],
                      child: const Center(
                          child: Text("",
                              style: TextStyle(fontWeight: FontWeight.bold))),
                    ),
                  ),
                ),
                const VerticalDivider(width: 1),
                // 滚轮 (简单实现：上下拖动)
                Expanded(
                  child: GestureDetector(
                    onVerticalDragUpdate: (details) {
                      // 向上滑 delta.dy 为负 -> 滚轮向上 (正数)
                      // 调整系数以获得舒适的滚动速度
                      int scrollAmount = (details.delta.dy * -1).toInt();
                      if (scrollAmount != 0) {
                        _sendCommand({
                          "type": "scroll",
                          "amount": scrollAmount
                        });
                      }
                    },
                    child: Container(
                      color: Colors.grey[100],
                      child: const Center(
                          child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.unfold_more),
                        ],
                      )),
                    ),
                  ),
                ),
                const VerticalDivider(width: 1),
                // 右键
                Expanded(
                  child: InkWell(
                    onTap: () =>
                        _sendCommand({"type": "click", "button": "right"}),
                    child: Container(
                      color: Colors.blue[50],
                      child: const Center(
                          child: Text("",
                              style: TextStyle(fontWeight: FontWeight.bold))),
                    ),
                  ),
                ),
              ],
            ),
          ),
          // 底部快捷键栏 (简单占位，暂未实现复杂逻辑)
          Container(
            height: 50,
            color: Colors.grey[300],
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _buildModifierKey("Esc", isToggle: false),
                _buildModifierKey("Ctrl", keyName: "ctrl"),
                _buildModifierKey("Alt", keyName: "alt"),
                // _buildModifierKey("Shift", keyName: "shift"),
                IconButton(
                  icon: const Icon(Icons.keyboard),
                  onPressed: () {
                    // 弹出软键盘输入
                    FocusScope.of(context).requestFocus(_textFocusNode);
                    // 清空之前的状态，防止逻辑错乱
                    _textController.clear();
                    _lastText = "";
                  },
                )
              ],
            ),
          )
        ],
      ),
    );
  }

  Widget _buildModifierKey(String label, {String? keyName, bool isToggle = true}) {
    // 如果没有指定 keyName，默认使用小写 label
    final String actualKey = keyName ?? label.toLowerCase();
    final bool isActive = _modifierKeys[actualKey] ?? false;

    return ElevatedButton(
      onPressed: () {
        if (!isToggle) {
          // 普通按键，直接点击
          _sendCommand({"type": "key", "key": actualKey});
        } else {
          // 切换型按键
          _toggleModifierKey(actualKey);
        }
      },
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        minimumSize: const Size(60, 40),
        backgroundColor: isActive ? Colors.blueAccent : null,
        foregroundColor: isActive ? Colors.white : null,
      ),
      child: Text(label),
    );
  }
}