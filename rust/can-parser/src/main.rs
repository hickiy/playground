use anyhow::Result;
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::net::SocketAddr;
use tokio::net::{TcpListener, TcpStream};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tracing::{info, error};

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// 监听端口
    #[arg(short, long, default_value = "8080")]
    port: u16,
    
    /// 监听地址
    #[arg(short, long, default_value = "127.0.0.1")]
    addr: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CanMessage {
    /// CAN ID
    pub id: u32,
    /// 数据长度
    pub dlc: u8,
    /// 数据内容（最多8字节）
    pub data: Vec<u8>,
    /// 是否为扩展帧
    pub extended: bool,
    /// 是否为远程帧
    pub remote: bool,
}

#[derive(Debug, Serialize, Deserialize)]
struct CanResponse {
    /// 解析状态
    pub status: String,
    /// 解析结果
    pub result: Option<ParsedCanData>,
    /// 错误信息
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct ParsedCanData {
    /// 原始CAN消息
    pub raw_message: CanMessage,
    /// 解析后的数据
    pub parsed_data: Vec<ParsedField>,
    /// 消息类型描述
    pub message_type: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct ParsedField {
    /// 字段名称
    pub name: String,
    /// 字段值
    pub value: String,
    /// 字段描述
    pub description: String,
    /// 字节位置
    pub byte_position: usize,
    /// 位位置（如果适用）
    pub bit_position: Option<u8>,
}

struct CanParser;

impl CanParser {
    /// 解析CAN消息
    pub fn parse_can_message(message: &CanMessage) -> Result<ParsedCanData> {
        let mut parsed_fields = Vec::new();
        let message_type = Self::identify_message_type(message.id);
        
        match message.id {
            // 引擎数据 (示例 ID: 0x7DF)
            0x7DF => {
                parsed_fields.extend(Self::parse_engine_data(&message.data)?);
            }
            // 车辆速度数据 (示例 ID: 0x7E0)
            0x7E0 => {
                parsed_fields.extend(Self::parse_vehicle_speed(&message.data)?);
            }
            // 传感器数据 (示例 ID: 0x123)
            0x123 => {
                parsed_fields.extend(Self::parse_sensor_data(&message.data)?);
            }
            // 默认通用解析
            _ => {
                parsed_fields.extend(Self::parse_generic_data(&message.data)?);
            }
        }
        
        Ok(ParsedCanData {
            raw_message: message.clone(),
            parsed_data: parsed_fields,
            message_type,
        })
    }
    
    /// 识别消息类型
    fn identify_message_type(can_id: u32) -> String {
        match can_id {
            0x7DF => "Engine Data".to_string(),
            0x7E0 => "Vehicle Speed".to_string(),
            0x123 => "Sensor Data".to_string(),
            0x100..=0x1FF => "System Control".to_string(),
            0x200..=0x2FF => "Body Control".to_string(),
            0x300..=0x3FF => "Chassis Control".to_string(),
            0x400..=0x4FF => "Powertrain".to_string(),
            0x500..=0x5FF => "Network Management".to_string(),
            0x600..=0x6FF => "Diagnostic".to_string(),
            0x700..=0x7FF => "Functional Addressing".to_string(),
            _ => format!("Unknown (ID: 0x{:X})", can_id),
        }
    }
    
    /// 解析引擎数据
    fn parse_engine_data(data: &[u8]) -> Result<Vec<ParsedField>> {
        let mut fields = Vec::new();
        
        if data.len() >= 2 {
            let rpm = ((data[0] as u16) << 8) | (data[1] as u16);
            fields.push(ParsedField {
                name: "Engine RPM".to_string(),
                value: format!("{} rpm", rpm),
                description: "Engine rotations per minute".to_string(),
                byte_position: 0,
                bit_position: None,
            });
        }
        
        if data.len() >= 4 {
            let load = data[2];
            fields.push(ParsedField {
                name: "Engine Load".to_string(),
                value: format!("{}%", (load as f32 / 255.0 * 100.0) as u8),
                description: "Engine load percentage".to_string(),
                byte_position: 2,
                bit_position: None,
            });
            
            let temp = data[3] as i16 - 40; // 温度偏移
            fields.push(ParsedField {
                name: "Coolant Temperature".to_string(),
                value: format!("{}°C", temp),
                description: "Engine coolant temperature".to_string(),
                byte_position: 3,
                bit_position: None,
            });
        }
        
        Ok(fields)
    }
    
    /// 解析车辆速度数据
    fn parse_vehicle_speed(data: &[u8]) -> Result<Vec<ParsedField>> {
        let mut fields = Vec::new();
        
        if data.len() >= 2 {
            let speed = ((data[0] as u16) << 8) | (data[1] as u16);
            fields.push(ParsedField {
                name: "Vehicle Speed".to_string(),
                value: format!("{} km/h", speed),
                description: "Current vehicle speed".to_string(),
                byte_position: 0,
                bit_position: None,
            });
        }
        
        if data.len() >= 4 {
            let wheel_speed_fl = ((data[2] as u16) << 8) | (data[3] as u16);
            fields.push(ParsedField {
                name: "Front Left Wheel Speed".to_string(),
                value: format!("{} km/h", wheel_speed_fl),
                description: "Front left wheel speed".to_string(),
                byte_position: 2,
                bit_position: None,
            });
        }
        
        Ok(fields)
    }
    
    /// 解析传感器数据
    fn parse_sensor_data(data: &[u8]) -> Result<Vec<ParsedField>> {
        let mut fields = Vec::new();
        
        if !data.is_empty() {
            let status_byte = data[0];
            
            // 解析状态位
            fields.push(ParsedField {
                name: "Door Status".to_string(),
                value: if status_byte & 0x01 != 0 { "Open" } else { "Closed" }.to_string(),
                description: "Front door status".to_string(),
                byte_position: 0,
                bit_position: Some(0),
            });
            
            fields.push(ParsedField {
                name: "Engine Status".to_string(),
                value: if status_byte & 0x02 != 0 { "Running" } else { "Off" }.to_string(),
                description: "Engine running status".to_string(),
                byte_position: 0,
                bit_position: Some(1),
            });
            
            fields.push(ParsedField {
                name: "Parking Brake".to_string(),
                value: if status_byte & 0x04 != 0 { "Engaged" } else { "Released" }.to_string(),
                description: "Parking brake status".to_string(),
                byte_position: 0,
                bit_position: Some(2),
            });
        }
        
        if data.len() >= 3 {
            let temp = ((data[1] as u16) << 8) | (data[2] as u16);
            let actual_temp = (temp as f32 / 10.0) - 40.0;
            fields.push(ParsedField {
                name: "Ambient Temperature".to_string(),
                value: format!("{:.1}°C", actual_temp),
                description: "Outside air temperature".to_string(),
                byte_position: 1,
                bit_position: None,
            });
        }
        
        Ok(fields)
    }
    
    /// 通用数据解析
    fn parse_generic_data(data: &[u8]) -> Result<Vec<ParsedField>> {
        let mut fields = Vec::new();
        
        for (i, &byte) in data.iter().enumerate() {
            fields.push(ParsedField {
                name: format!("Byte {}", i),
                value: format!("0x{:02X} ({})", byte, byte),
                description: format!("Raw data byte at position {}", i),
                byte_position: i,
                bit_position: None,
            });
        }
        
        Ok(fields)
    }
    
    /// 从十六进制字符串解析CAN消息
    pub fn parse_hex_string(hex_str: &str) -> Result<CanMessage> {
        let parts: Vec<&str> = hex_str.trim().split_whitespace().collect();
        
        if parts.len() < 2 {
            return Err(anyhow::anyhow!("Invalid format. Expected: <CAN_ID> <DATA_BYTES>"));
        }
        
        // 解析 CAN ID
        let id_str = parts[0];
        let id = if id_str.starts_with("0x") || id_str.starts_with("0X") {
            u32::from_str_radix(&id_str[2..], 16)?
        } else {
            u32::from_str_radix(id_str, 16)?
        };
        
        // 解析数据字节
        let mut data = Vec::new();
        for part in &parts[1..] {
            let byte_str = if part.starts_with("0x") || part.starts_with("0X") {
                &part[2..]
            } else {
                part
            };
            
            if byte_str.len() == 2 {
                data.push(u8::from_str_radix(byte_str, 16)?);
            } else if byte_str.len() % 2 == 0 {
                // 处理连续的十六进制字符串
                for i in (0..byte_str.len()).step_by(2) {
                    data.push(u8::from_str_radix(&byte_str[i..i+2], 16)?);
                }
            }
        }
        
        if data.len() > 8 {
            return Err(anyhow::anyhow!("CAN data cannot exceed 8 bytes"));
        }
        
        Ok(CanMessage {
            id,
            dlc: data.len() as u8,
            data,
            extended: id > 0x7FF,
            remote: false,
        })
    }
}

async fn handle_client(stream: TcpStream, addr: SocketAddr) -> Result<()> {
    info!("New client connected: {}", addr);
    
    let (reader, mut writer) = stream.into_split();
    let mut buf_reader = BufReader::new(reader);
    let mut line = String::new();
    
    // 发送欢迎消息
    let welcome = "CAN Parser Service v1.0\nSend CAN data in format: <CAN_ID> <DATA_BYTES>\nExample: 0x123 01 02 03 04\nType 'quit' to exit.\n> ";
    writer.write_all(welcome.as_bytes()).await?;
    
    loop {
        line.clear();
        
        match buf_reader.read_line(&mut line).await {
            Ok(0) => {
                info!("Client {} disconnected", addr);
                break;
            }
            Ok(_) => {
                let input = line.trim();
                
                if input.eq_ignore_ascii_case("quit") || input.eq_ignore_ascii_case("exit") {
                    info!("Client {} requested disconnect", addr);
                    break;
                }
                
                if input.is_empty() {
                    writer.write_all(b"> ").await?;
                    continue;
                }
                
                // 解析并处理CAN消息
                let response = match CanParser::parse_hex_string(input) {
                    Ok(can_msg) => {
                        match CanParser::parse_can_message(&can_msg) {
                            Ok(parsed_data) => CanResponse {
                                status: "success".to_string(),
                                result: Some(parsed_data),
                                error: None,
                            },
                            Err(e) => CanResponse {
                                status: "parse_error".to_string(),
                                result: None,
                                error: Some(format!("Failed to parse CAN data: {}", e)),
                            }
                        }
                    }
                    Err(e) => CanResponse {
                        status: "format_error".to_string(),
                        result: None,
                        error: Some(format!("Invalid input format: {}", e)),
                    }
                };
                
                // 发送JSON响应
                let json_response = serde_json::to_string_pretty(&response)?;
                writer.write_all(json_response.as_bytes()).await?;
                writer.write_all(b"\n> ").await?;
            }
            Err(e) => {
                error!("Error reading from client {}: {}", addr, e);
                break;
            }
        }
    }
    
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    // 初始化日志
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .init();
    
    let args = Args::parse();
    let listen_addr = format!("{}:{}", args.addr, args.port);
    
    info!("Starting CAN Parser Service on {}", listen_addr);
    
    let listener = TcpListener::bind(&listen_addr).await?;
    info!("Server listening on {}", listen_addr);
    
    loop {
        match listener.accept().await {
            Ok((stream, addr)) => {
                tokio::spawn(async move {
                    if let Err(e) = handle_client(stream, addr).await {
                        error!("Error handling client {}: {}", addr, e);
                    }
                });
            }
            Err(e) => {
                error!("Failed to accept connection: {}", e);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_parse_hex_string() {
        let result = CanParser::parse_hex_string("0x123 01 02 03 04").unwrap();
        assert_eq!(result.id, 0x123);
        assert_eq!(result.data, vec![0x01, 0x02, 0x03, 0x04]);
        assert_eq!(result.dlc, 4);
    }
    
    #[test]
    fn test_parse_engine_data() {
        let message = CanMessage {
            id: 0x7DF,
            dlc: 4,
            data: vec![0x10, 0x00, 0x80, 0x50], // RPM: 4096, Load: 50%, Temp: 40°C
            extended: false,
            remote: false,
        };
        
        let result = CanParser::parse_can_message(&message).unwrap();
        assert_eq!(result.message_type, "Engine Data");
        assert!(!result.parsed_data.is_empty());
    }
    
    #[test]
    fn test_parse_sensor_data() {
        let message = CanMessage {
            id: 0x123,
            dlc: 3,
            data: vec![0x07, 0x02, 0x80], // 状态字节和温度数据
            extended: false,
            remote: false,
        };
        
        let result = CanParser::parse_can_message(&message).unwrap();
        assert_eq!(result.message_type, "Sensor Data");
        assert!(!result.parsed_data.is_empty());
    }
}
