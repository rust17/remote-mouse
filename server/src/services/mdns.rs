use mdns_sd::{ServiceDaemon, ServiceInfo};
use std::collections::HashMap;
use tracing::{error, info};

pub struct MDNSResponder {
    port: u16,
    _daemon: Option<ServiceDaemon>,
}

impl MDNSResponder {
    pub fn new(port: u16) -> Self {
        Self {
            port,
            _daemon: None,
        }
    }

    pub fn start(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        let mdns = ServiceDaemon::new()?;
        let service_type = "_http._tcp.local.";
        let instance_name = "Remote Mouse Service";
        let host_name = "remote-mouse.local.";
        let port = self.port;

        // 获取本机 IP
        let ip = match local_ip_address::local_ip() {
            Ok(ip) => ip.to_string(),
            Err(e) => {
                error!("Could not get local IP: {}", e);
                return Err(e.into());
            }
        };

        info!(
            "Registering mDNS service [{}] at {}:{} (host: {})",
            instance_name, ip, port, host_name
        );

        let properties = HashMap::new();
        let service_info = ServiceInfo::new(
            service_type,
            instance_name,
            host_name,
            &ip,
            port,
            properties,
        )?;

        mdns.register(service_info)?;

        self._daemon = Some(mdns);
        Ok(())
    }
}
