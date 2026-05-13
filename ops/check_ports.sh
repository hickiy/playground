#!/bin/bash
# =============================================================================
# 脚本名称: check_ports.sh
# 功    能: 扫描目标服务器的常见 TCP 端口，找出可连接的服务端口
# 作    用: 当 SSH 无法连接但服务器可 ping 通时，用于定位备用控制入口
# 使用示例: ./check_ports.sh 192.168.1.100
# =============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -eq 0 ]; then
    echo -e "${RED}用法: $0 <服务器IP>${NC}"
    echo "示例: $0 192.168.1.100"
    exit 1
fi

TARGET_IP="$1"
echo -e "${YELLOW}>> 开始扫描目标: $TARGET_IP ${NC}\n"

# -------------------------------------------------------------------------
# 1. 定义需要探测的常见端口列表
#    (可根据实际情况增删)
# -------------------------------------------------------------------------
COMMON_PORTS=(
    # 系统基础服务
    21      # FTP
    22      # SSH (默认)
    23      # Telnet
    3389    # RDP (Windows远程桌面)
    5900    # VNC
    5901    # VNC :1

    # Web 服务
    80      # HTTP
    443     # HTTPS
    8080    # HTTP 备用 / 部分面板
    8443    # HTTPS 备用

    # Linux 面板类
    8888    # 宝塔面板 (BT)
    9999    # AMH面板 / 部分自定义
    8081    # 一些面板备用
    10000   # Virtualmin / Webmin
    888     # 一些自定义面板

    # 数据库
    3306    # MySQL
    5432    # PostgreSQL
    6379    # Redis

    # 邮件服务
    25      # SMTP
    110     # POP3
    143     # IMAP

    # 其他运维工具
    2222    # 自定义 SSH 常见端口
    10022   # 自定义 SSH
    8022    # 自定义 SSH
    9090    # Cockpit 等
    8088    # 一些代理面板
)

# 如果你希望扫描 1-1024 所有端口（耗时较长，谨慎使用），把下面这行取消注释：
# PORTS=$(seq 1 1024)
# 这里我们只扫描上述列表，快速获得结果
PORTS=("${COMMON_PORTS[@]}")

# -------------------------------------------------------------------------
# 2. 定义端口连通性检测函数（使用 /dev/tcp，无需额外工具）
# -------------------------------------------------------------------------
test_port() {
    local host="$1"
    local port="$2"
    timeout 1 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null
    return $?
}

# -------------------------------------------------------------------------
# 3. 依次检测每个端口，收集结果
# -------------------------------------------------------------------------
open_ports=()
for port in "${PORTS[@]}"; do
    printf "检测端口 %5d ... " "$port"
    if test_port "$TARGET_IP" "$port"; then
        echo -e "${GREEN}开放${NC}"
        open_ports+=("$port")
    else
        echo -e "关闭"
    fi
done

# -------------------------------------------------------------------------
# 4. 汇总结果并给出建议
# -------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}========== 扫描完成 ==========${NC}"

if [ ${#open_ports[@]} -eq 0 ]; then
    echo -e "${RED}未发现任何可连接的 TCP 端口。${NC}"
    echo -e "可能原因："
    echo "  1. 服务器防火墙阻止了所有入站连接（包括 ICMP 虽通但 TCP 被拦）"
    echo "  2. 服务器网络配置异常（检查路由、网关）"
    echo "  3. 服务未启动"
    echo ""
    echo -e "${YELLOW}建议：${NC}"
    echo "  - 使用戴尔服务器的 iDRAC 管理口（独立IP）或物理 KVM 进入系统检查"
    echo "  - 如果无带外管理，请联系机房协助挂载救援系统"
    exit 1
else
    echo -e "${GREEN}发现以下端口开放：${open_ports[@]}${NC}"
    echo ""
    echo -e "${YELLOW}>>> 建议的登录/控制方式 <<<${NC}"

    # 对每个开放端口给出可能的服务提示
    for p in "${open_ports[@]}"; do
        case $p in
            22)
                echo -e "  * 端口 ${GREEN}22${NC} : SSH 默认端口 → 尝试命令: ssh root@$TARGET_IP"
                ;;
            2222|10022|8022)
                echo -e "  * 端口 ${GREEN}$p${NC} : 可能是自定义 SSH 端口 → 尝试: ssh -p $p root@$TARGET_IP"
                ;;
            8888)
                echo -e "  * 端口 ${GREEN}8888${NC} : 宝塔面板 (BT) → 浏览器访问 http://$TARGET_IP:8888"
                ;;
            8080|888|9999|8081|10000|9090)
                echo -e "  * 端口 ${GREEN}$p${NC} : 常见 Web 控制面板端口 → 浏览器访问 http://$TARGET_IP:$p"
                ;;
            80|443)
                echo -e "  * 端口 ${GREEN}$p${NC} : Web 服务 → 浏览器访问 http${p==443? s: ''}://$TARGET_IP"
                ;;
            3306)
                echo -e "  * 端口 ${GREEN}3306${NC} : MySQL 数据库 → 可尝试远程连接（需账号权限）"
                ;;
            3389)
                echo -e "  * 端口 ${GREEN}3389${NC} : Windows 远程桌面 → 使用 RDP 客户端连接"
                ;;
            5900|5901)
                echo -e "  * 端口 ${GREEN}$p${NC} : VNC 远程桌面 → 使用 VNC Viewer 连接 $TARGET_IP:$((p-5900))"
                ;;
            21)
                echo -e "  * 端口 ${GREEN}21${NC} : FTP 服务 → 可尝试使用 ftp 客户端"
                ;;
            *)
                echo -e "  * 端口 ${GREEN}$p${NC} : 未知服务，可用 telnet $TARGET_IP $p 或 nc -vz $TARGET_IP $p 进一步探测"
                ;;
        esac
    done

    echo ""
    echo -e "${YELLOW}如果以上端口均无法进入系统，请考虑：${NC}"
    echo "  - 通过戴尔 iDRAC 的虚拟控制台直接登录（独立于操作系统）"
    echo "  - 使用救援模式/挂载 ISO 修复 SSH 配置"
fi