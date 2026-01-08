import socket
from zeroconf import IPVersion, ServiceInfo, Zeroconf
import logging
import ifaddr

from loguru import logger


class MDNSResponder:
    def __init__(self, service_name="Remote Mouse", port=9997):
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.service_name = service_name
        self.port = port
        self.service_info = None

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
        s.close()

        return ip

    def register(self):
        # mDNS 规范要求主机名以 .local. 结尾
        # 用户直接输入 remote-mouse.local 需要该域名解析到 IP
        hostname = "remote-mouse.local."

        local_ip = self.get_local_ip()
        logger.info(f"Detected Local IP: {local_ip}")

        # 服务类型必须是 _http._tcp.local.
        # 我们注册一个固定的服务名以便发现，但也包含主机名以防冲突
        service_type = "_http._tcp.local."
        service_name = f"RemoteMouse Service.{service_type}"

        self.service_info = ServiceInfo(
            service_type,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={"path": "/"},
            server=hostname,
        )

        logger.info(
            f"Registering mDNS service: {service_name} pointing to {hostname} ({local_ip}:{self.port})"
        )
        try:
            self.zeroconf.register_service(self.service_info)
        except Exception as e:
            logger.error(f"Failed to register mDNS: {e}")

    def unregister(self):
        if self.service_info:
            logger.info("Unregistering mDNS service")
            self.zeroconf.unregister_service(self.service_info)
        self.zeroconf.close()
