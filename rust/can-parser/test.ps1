# CAN 解析服务测试脚本

# 启动服务器（在后台运行）
echo "启动 CAN 解析服务..."
Start-Process -FilePath "cargo" -ArgumentList "run" -WindowStyle Hidden

# 等待服务器启动
Start-Sleep 3

# 测试数据
$testData = @(
    "0x7DF 10 00 80 50",  # 引擎数据
    "0x7E0 00 3C 00 3A",  # 车辆速度
    "0x123 07 02 80",     # 传感器数据
    "0x456 01 02 03 04 05 06 07 08"  # 通用数据
)

echo "测试 CAN 数据解析..."

foreach ($data in $testData) {
    echo "测试数据: $data"
    
    # 使用 telnet 或 nc 工具连接并发送数据
    # 这里使用 PowerShell 的 TcpClient
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect("127.0.0.1", 8080)
    $stream = $client.GetStream()
    $writer = New-Object System.IO.StreamWriter($stream)
    $reader = New-Object System.IO.StreamReader($stream)
    
    # 读取欢迎消息
    $welcome = $reader.ReadLine()
    echo $welcome
    
    # 发送测试数据
    $writer.WriteLine($data)
    $writer.Flush()
    
    # 读取响应
    $response = ""
    do {
        $line = $reader.ReadLine()
        $response += $line + "`n"
    } while ($line -notmatch ">$")
    
    echo "响应:"
    echo $response
    echo "-------------------"
    
    $client.Close()
    Start-Sleep 1
}

echo "测试完成！"
