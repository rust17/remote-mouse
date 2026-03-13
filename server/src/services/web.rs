use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::{Html, IntoResponse, Response},
    routing::get,
    Router,
};
use rust_embed::RustEmbed;
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::mpsc;
use tracing::{error, info};

use crate::core::protocol::{parse_command, ProtocolCommand};

#[derive(RustEmbed)]
#[folder = "../web-client/dist/"]
struct Assets;

struct AppState {
    tx: mpsc::UnboundedSender<ProtocolCommand>,
}

pub struct WebService {
    port: u16,
    tx: mpsc::UnboundedSender<ProtocolCommand>,
}

impl WebService {
    pub fn new(port: u16, tx: mpsc::UnboundedSender<ProtocolCommand>) -> Self {
        Self { port, tx }
    }

    pub async fn start(self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let state = Arc::new(AppState { tx: self.tx });

        let app = Router::new()
            .route("/ws", get(ws_handler))
            .fallback(static_handler)
            .with_state(state);

        let addr = SocketAddr::from(([0, 0, 0, 0], self.port));
        let listener = tokio::net::TcpListener::bind(addr).await?;
        info!("Web server listening on {}", addr);

        axum::serve(listener, app).await?;
        Ok(())
    }
}

async fn ws_handler(
    ws: WebSocketUpgrade,
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_socket(socket, state))
}

async fn handle_socket(mut socket: WebSocket, state: Arc<AppState>) {
    info!("WebSocket client connected");
    while let Some(Ok(msg)) = socket.recv().await {
        if let Message::Binary(data) = msg {
            if let Some(cmd) = parse_command(&data) {
                // 将解析出的指令发送给同步输入控制线程
                if let Err(e) = state.tx.send(cmd) {
                    error!("Failed to send command to input thread: {}", e);
                    break;
                }
            }
        }
    }
    info!("WebSocket client disconnected");
}

async fn static_handler(req: axum::http::Request<axum::body::Body>) -> impl IntoResponse {
    let path = req.uri().path().trim_start_matches('/');
    
    // 如果路径为空，默认提供 index.html
    let asset_path = if path.is_empty() { "index.html" } else { path };

    match Assets::get(asset_path) {
        Some(content) => {
            let mime = mime_guess::from_path(asset_path).first_or_octet_stream();
            Response::builder()
                .header(axum::http::header::CONTENT_TYPE, mime.as_ref())
                .body(axum::body::Body::from(content.data))
                .unwrap()
        }
        None => {
            // SPA Fallback: 如果资源不存在，返回 index.html
            if let Some(index) = Assets::get("index.html") {
                Response::builder()
                    .header(axum::http::header::CONTENT_TYPE, "text/html")
                    .body(axum::body::Body::from(index.data))
                    .unwrap()
            } else {
                Response::builder()
                    .status(axum::http::StatusCode::NOT_FOUND)
                    .body(axum::body::Body::from("404 Not Found"))
                    .unwrap()
            }
        }
    }
}
