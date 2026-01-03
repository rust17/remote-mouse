import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
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
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLoopback: false,
      );

      String? localIp;
      String? broadcastIp;

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
        // print("未找到合适的网络接口");
        return;
      }

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
              // print("UDP 解析错误: $e");
            }
          }
        }
      });

      final data = utf8.encode("SCAN_REMOTE_MOUSE");
      for (int i = 0; i < 3; i++) {
        _udpSocket?.send(data, InternetAddress(broadcastIp), 9999);
        await Future.delayed(const Duration(milliseconds: 500));
      }
    } catch (e) {
      // print("扫描出错: $e");
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

  // 设置参数
  double _moveSensitivity = 2.0;
  double _scrollSensitivity = 1.0;

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

  // 触摸板状态
  final Map<int, Offset> _activePointers = {};
  Offset? _lastCentroid;
  int _maxPointers = 0;
  bool _hasMoved = false;
  bool _isDragging = false;
  
  // 滚动累加器
  double _scrollAccumulatorY = 0.0;
  double _scrollAccumulatorX = 0.0;

  // 移动累加器
  double _moveAccumulatorX = 0.0;
  double _moveAccumulatorY = 0.0;

  // 拖拽延时结束计时器
  Timer? _dragEndTimer;

  // 移动指令节流 (Throttling)
  int _pendingDx = 0;
  int _pendingDy = 0;
  Timer? _moveThrottleTimer;
  DateTime _lastSendTime = DateTime.fromMillisecondsSinceEpoch(0);


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
    _moveThrottleTimer?.cancel();
    super.dispose();
  }

  Future<void> _connectToServer() async {
    try {
      _socket = await Socket.connect(widget.serverIp, widget.serverPort);
      _socket!.setOption(SocketOption.tcpNoDelay, true); // 禁用 Nagle 算法，降低延迟
      
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
        _modifierKeys.updateAll((key, value) => false);
      });
    }
  }

  void _sendCommand(Map<String, dynamic> cmd) {
    if (_socket != null && _isConnected) {
      try {
        _socket!.write(jsonEncode(cmd) + "\n");
      } catch (e) {
        // print("发送失败: $e");
      }
    }
  }

  void _flushPendingMove() {
    if (_pendingDx != 0 || _pendingDy != 0) {
      _sendCommand({
        "type": "move",
        "dx": _pendingDx,
        "dy": _pendingDy
      });
      _pendingDx = 0;
      _pendingDy = 0;
      _lastSendTime = DateTime.now();
    }
    _moveThrottleTimer = null;
  }

  void _handleTextChange(String newText) {
    if (newText.length > _lastText.length) {
      String diff = newText.substring(_lastText.length);
      _sendCommand({"type": "text", "text": diff});
    } else if (newText.length < _lastText.length) {
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
    _sendCommand({"type": isActive ? "keyUp" : "keyDown", "key": key});
  }

  void _showSettings() {
    showModalBottomSheet(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Container(
              padding: const EdgeInsets.all(20),
              height: 250,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("设置", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 20),
                  Text("移动灵敏度: ${_moveSensitivity.toStringAsFixed(1)}"),
                  Slider(
                    value: _moveSensitivity,
                    min: 0.5,
                    max: 10.0,
                    divisions: 19,
                    label: _moveSensitivity.toStringAsFixed(1),
                    onChanged: (value) {
                      setState(() => _moveSensitivity = value); // 更新主页面状态
                      setSheetState(() => _moveSensitivity = value); // 更新 Sheet 状态
                    },
                  ),
                  Text("滚动灵敏度: ${_scrollAccumulatorY.toStringAsFixed(1)}"), 
                  // 这里用 _scrollSensitivity 变量名，UI 显示稍微修饰下
                   Slider(
                    value: _scrollSensitivity,
                    min: 0.1,
                    max: 5.0,
                    divisions: 49,
                    label: _scrollSensitivity.toStringAsFixed(1),
                    onChanged: (value) {
                      setState(() => _scrollSensitivity = value);
                      setSheetState(() => _scrollSensitivity = value);
                    },
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  // ---

  Offset _calculateCentroid() {
    if (_activePointers.isEmpty) return Offset.zero;
    double sumX = 0, sumY = 0;
    for (var pos in _activePointers.values) {
      sumX += pos.dx;
      sumY += pos.dy;
    }
    return Offset(sumX / _activePointers.length, sumY / _activePointers.length);
  }

  void _onPointerDown(PointerDownEvent event) {
    _activePointers[event.pointer] = event.position;
    _maxPointers = max(_maxPointers, _activePointers.length);
    _lastCentroid = _calculateCentroid();
    _hasMoved = false;

    // 如果三指落下，且正在等待结束拖拽，则恢复拖拽（取消计时器）
    if (_activePointers.length == 3 && _isDragging) {
      _dragEndTimer?.cancel();
      _dragEndTimer = null;
    }
  }

  void _onPointerMove(PointerMoveEvent event) {
    _activePointers[event.pointer] = event.position;
    final newCentroid = _calculateCentroid();
    
    if (_lastCentroid != null) {
      final dx = newCentroid.dx - _lastCentroid!.dx;
      final dy = newCentroid.dy - _lastCentroid!.dy;
      
      int count = _activePointers.length;
      
      // 如果正在拖拽，即使只有 1 或 2 指，也优先保持移动而非滚动
      if (count == 3 || (count > 0 && _isDragging) || count == 1) {
        // 开启/恢复拖拽
        if (count == 3) {
          if (!_isDragging) {
            _sendCommand({"type": "drag_start"});
            _isDragging = true;
          }
          _dragEndTimer?.cancel();
          _dragEndTimer = null;
        }

        // 优化：如果是拖拽状态但手指少于3个（正在抬起手指），则暂停光标移动，防止"滑冰"效应
        // 只有当 (正在拖拽且手指>=3) 或者 (非拖拽且手指==1) 时才移动
        bool shouldMove = (_isDragging && count >= 3) || (!_isDragging && count == 1);

        if (shouldMove) {
          _moveAccumulatorX += dx * _moveSensitivity;
          _moveAccumulatorY += dy * _moveSensitivity;

          int sendDx = _moveAccumulatorX.truncate();
          int sendDy = _moveAccumulatorY.truncate();

          if (sendDx != 0 || sendDy != 0) {
            _hasMoved = true;
            _pendingDx += sendDx;
            _pendingDy += sendDy;
            _moveAccumulatorX -= sendDx;
            _moveAccumulatorY -= sendDy;

            final now = DateTime.now();
            final timeSinceLastSend = now.difference(_lastSendTime).inMilliseconds;

            if (timeSinceLastSend >= 16) {
              // 超过 16ms，立即发送
              _flushPendingMove();
            } else {
              // 没超过 16ms，且没有定时器在跑，则启动定时器在剩余时间后发送
              if (_moveThrottleTimer == null || !_moveThrottleTimer!.isActive) {
                _moveThrottleTimer = Timer(
                  Duration(milliseconds: 16 - timeSinceLastSend),
                  _flushPendingMove,
                );
              }
            }
          }
        }
      } else if (count == 2) {
        // 双指滚动
        double step = 20.0 / _scrollSensitivity;
        _scrollAccumulatorY += dy;
        _scrollAccumulatorX += dx;

        if (_scrollAccumulatorY.abs() >= step) {
           _hasMoved = true;
           int clicks = -(_scrollAccumulatorY / step).truncate();
           _sendCommand({"type": "scroll", "amount": clicks});
           _scrollAccumulatorY = _scrollAccumulatorY % step;
        }
      }
    }
    
    _lastCentroid = newCentroid;
  }

  void _onPointerUp(PointerUpEvent event) {
    _activePointers.remove(event.pointer);
    
    // 手指抬起，立即发送所有积压的移动
    _flushPendingMove();

    // 三指拖拽缓冲：手指抬起导致少于3指时，不立即结束，等待一小会儿
    if (_isDragging && _activePointers.length < 3) {
      _dragEndTimer?.cancel();
      _dragEndTimer = Timer(const Duration(milliseconds: 300), () {
        if (_activePointers.length < 3) {
          _sendCommand({"type": "drag_end"});
          _isDragging = false;
        }
      });
    }
    
    if (_activePointers.isEmpty) {
      // 如果所有手指都抬起了，立即结束拖拽
      if (_isDragging) {
        _dragEndTimer?.cancel();
        _sendCommand({"type": "drag_end"});
        _isDragging = false;
      }

      if (!_hasMoved) {
        if (_maxPointers == 1) {
          _sendCommand({"type": "click", "button": "left"});
        } else if (_maxPointers == 2) {
          _sendCommand({"type": "click", "button": "right"});
        }
      }
      
      // 重置状态
      _maxPointers = 0;
      _hasMoved = false;
      _scrollAccumulatorY = 0;
      _scrollAccumulatorX = 0;
      _moveAccumulatorX = 0;
      _moveAccumulatorY = 0;
      _lastCentroid = null;
    } else {
      _lastCentroid = _calculateCentroid();
    }
  }
  
  void _onPointerCancel(PointerCancelEvent event) {
     _activePointers.remove(event.pointer);
     _flushPendingMove(); // 取消时也发送剩余移动
     if (_activePointers.isEmpty) {
        if (_isDragging) {
             _sendCommand({"type": "drag_end"});
             _isDragging = false;
        }
        _maxPointers = 0;
        _lastCentroid = null;
     } else {
        _lastCentroid = _calculateCentroid();
     }
  }


  @override
  Widget build(BuildContext context) {
    final orientation = MediaQuery.of(context).orientation;
    final isLandscape = orientation == Orientation.landscape;

    Widget touchPad = Listener(
      onPointerDown: _onPointerDown,
      onPointerMove: _onPointerMove,
      onPointerUp: _onPointerUp,
      onPointerCancel: _onPointerCancel,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: double.infinity,
        height: double.infinity,
        color: Colors.grey[900], // 深色背景模拟触控板
        child: const Center(
          child: Icon(Icons.touch_app, color: Colors.white12, size: 100),
        ),
      ),
    );

    Widget modifiersBar = Container(
       color: Colors.grey[850],
       padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
       child: isLandscape 
         ? Column(
             mainAxisAlignment: MainAxisAlignment.spaceEvenly,
             children: _buildModifierButtons(vertical: true),
           )
         : Row(
             mainAxisAlignment: MainAxisAlignment.spaceEvenly,
             children: _buildModifierButtons(vertical: false),
           ),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(_isConnected ? '已连接' : '未连接'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: _showSettings,
          )
        ],
      ),
      body: Column(
        children: [
          // 隐形输入框
          Offstage(
            offstage: true,
            child: TextField(
              controller: _textController,
              focusNode: _textFocusNode,
              autocorrect: false,
              enableSuggestions: false,
              keyboardType: TextInputType.visiblePassword,
              onChanged: _handleTextChange,
            ),
          ),
          
          Expanded(
            child: isLandscape
                ? Row(
                    children: [Expanded(child: touchPad), modifiersBar],
                  )
                : Column(
                    children: [Expanded(child: touchPad), modifiersBar],
                  ),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildModifierButtons({required bool vertical}) {
    final buttons = [
      _buildKeyBtn("Esc", isToggle: false),
      _buildKeyBtn("Ctrl", keyName: "ctrl"),
      _buildKeyBtn("Alt", keyName: "alt"),
      _buildKeyBtn("Shift", keyName: "shift"),
      _buildKeyBtn("Win", keyName: "command"),
      IconButton(
        icon: const Icon(Icons.keyboard, color: Colors.white),
        onPressed: () {
          FocusScope.of(context).requestFocus(_textFocusNode);
          _textController.clear();
          _lastText = "";
        },
      )
    ];
    
    return buttons.map((w) => Padding(
      padding: EdgeInsets.symmetric(
        horizontal: vertical ? 0 : 4, 
        vertical: vertical ? 4 : 0
      ),
      child: w
    )).toList();
  }
  
  Widget _buildKeyBtn(String label, {String? keyName, bool isToggle = true}) {
    final String actualKey = keyName ?? label.toLowerCase();
    final bool isActive = _modifierKeys[actualKey] ?? false;
    
    return ElevatedButton(
      onPressed: () {
        if (!isToggle) {
          _sendCommand({"type": "key", "key": actualKey});
        } else {
          _toggleModifierKey(actualKey);
        }
      },
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.all(12),
        minimumSize: const Size(50, 40),
        backgroundColor: isActive ? Colors.blueAccent : Colors.grey[700],
        foregroundColor: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
      child: Text(label),
    );
  }
}
