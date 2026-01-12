import socket
from zeroconf import IPVersion, ServiceInfo, Zeroconf
from loguru import logger

from server.config import APP_NAME, DEFAULT_PORT, MDNS_HOSTNAME


class MDNSResponder:
    SERVICE_TYPE = "_http._tcp.local."
    TEST_CONN_IP = "8.8.8.8"
    TEST_CONN_PORT = 1

    def __init__(self, service_name=APP_NAME, port=DEFAULT_PORT, hostname=MDNS_HOSTNAME):
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.service_name_base = service_name
        self.hostname = hostname
        self.port = port
        self.service_info = None

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((self.TEST_CONN_IP, self.TEST_CONN_PORT))
        ip = s.getsockname()[0]
        s.close()

        return ip

    def register(self):
        # mDNS 规范要求主机名以 .local. 结尾
        # 用户直接输入 remote-mouse.local 需要该域名解析到 IP

        local_ip = self.get_local_ip()
        logger.info(f"Detected Local IP: {local_ip}")

        # 我们注册一个固定的服务名以便发现，但也包含主机名以防冲突
        service_name = f"{self.service_name_base} Service.{self.SERVICE_TYPE}"

        self.service_info = ServiceInfo(
            self.SERVICE_TYPE,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={"path": "/"},
            server=self.hostname,
        )

        logger.info(
            f"Registering mDNS service: {service_name} pointing to {self.hostname} ({local_ip}:{self.port})"
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
