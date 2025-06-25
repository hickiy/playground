# CAN 协议数据包解析服务

这是一个基于 Rust 开发的 CAN 协议数据包解析服务，能够通过网络接收 CAN 数据并进行智能解析。

## 功能特性

- 🚀 异步网络服务，支持多客户端连接
- 📊 智能 CAN 数据解析，支持多种消息类型
- 🔍 详细的字段解析和描述
- 📡 JSON 格式响应，便于集成
- 🛠️ 支持自定义 CAN ID 和数据格式
- 📝 完整的日志记录

## 支持的 CAN 消息类型

| CAN ID | 消息类型 | 描述 |
|--------|----------|------|
| 0x7DF | Engine Data | 引擎数据（转速、负载、温度） |
| 0x7E0 | Vehicle Speed | 车辆速度数据 |
| 0x123 | Sensor Data | 传感器数据（门状态、温度等） |
| 0x100-0x1FF | System Control | 系统控制消息 |
| 0x200-0x2FF | Body Control | 车身控制消息 |
| 其他 | Generic | 通用解析 |

## 安装和运行

### 1. 构建项目

```bash
cargo build --release
```

### 2. 运行服务器

```bash
# 使用默认配置（127.0.0.1:8080）
cargo run

# 自定义端口和地址
cargo run -- --addr 0.0.0.0 --port 9090
```

### 3. 运行客户端（可选）

```bash
cargo run --bin client
```

## 使用方法

### 通过 TCP 连接

连接到服务器后，发送 CAN 数据格式：

```
<CAN_ID> <DATA_BYTES>
```

### 示例输入

```bash
# 引擎数据示例
0x7DF 10 00 80 50

# 车辆速度示例
0x7E0 00 3C 00 3A

# 传感器数据示例
0x123 07 02 80

# 扩展帧示例
0x1FFFFFFF 01 02 03 04 05 06 07 08
```

### 示例响应

```json
{
  "status": "success",
  "result": {
    "raw_message": {
      "id": 2015,
      "dlc": 4,
      "data": [16, 0, 128, 80],
      "extended": false,
      "remote": false
    },
    "parsed_data": [
      {
        "name": "Engine RPM",
        "value": "4096 rpm",
        "description": "Engine rotations per minute",
        "byte_position": 0,
        "bit_position": null
      },
      {
        "name": "Engine Load",
        "value": "50%",
        "description": "Engine load percentage",
        "byte_position": 2,
        "bit_position": null
      },
      {
        "name": "Coolant Temperature",
        "value": "40°C",
        "description": "Engine coolant temperature",
        "byte_position": 3,
        "bit_position": null
      }
    ],
    "message_type": "Engine Data"
  },
  "error": null
}
```

## 数据格式说明

### 引擎数据 (0x7DF)
- 字节 0-1: 引擎转速 (RPM)，大端序
- 字节 2: 引擎负载百分比 (0-255 对应 0-100%)
- 字节 3: 冷却液温度 (实际温度 = 值 - 40°C)

### 车辆速度 (0x7E0)
- 字节 0-1: 车辆速度 (km/h)，大端序
- 字节 2-3: 前左轮速度 (km/h)，大端序

### 传感器数据 (0x123)
- 字节 0 位0: 门状态 (0=关闭, 1=打开)
- 字节 0 位1: 引擎状态 (0=关闭, 1=运行)
- 字节 0 位2: 手刹状态 (0=释放, 1=拉起)
- 字节 1-2: 环境温度，大端序 (实际温度 = 值/10 - 40°C)

## 命令行参数

```bash
Usage: can-parser [OPTIONS]

Options:
  -p, --port <PORT>  监听端口 [default: 8080]
  -a, --addr <ADDR>  监听地址 [default: 127.0.0.1]
  -h, --help         Print help
  -V, --version      Print version
```

## 错误处理

服务会返回不同的错误状态：

- `format_error`: 输入格式错误
- `parse_error`: CAN 数据解析错误
- `success`: 解析成功

## 扩展开发

### 添加新的 CAN 消息类型

1. 在 `identify_message_type` 函数中添加新的 CAN ID 范围
2. 在 `parse_can_message` 函数中添加新的解析逻辑
3. 实现对应的解析函数

```rust
// 添加新的消息类型解析
0x500 => {
    parsed_fields.extend(Self::parse_new_message_type(&message.data)?);
}
```

### 自定义解析逻辑

创建新的解析函数：

```rust
fn parse_new_message_type(data: &[u8]) -> Result<Vec<ParsedField>> {
    let mut fields = Vec::new();
    
    // 添加你的解析逻辑
    if data.len() >= 2 {
        let value = ((data[0] as u16) << 8) | (data[1] as u16);
        fields.push(ParsedField {
            name: "Custom Field".to_string(),
            value: format!("{}", value),
            description: "Custom field description".to_string(),
            byte_position: 0,
            bit_position: None,
        });
    }
    
    Ok(fields)
}
```

## 测试

运行测试：

```bash
cargo test
```

## 许可证

MIT License
