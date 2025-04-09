#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import time
import re
from datetime import datetime, timedelta
import requests
import tempfile
import getpass
import shutil

# 当前日期
CURRENT_DATE = datetime.now().strftime("%Y-%m-%d")

# 检查命令是否成功执行
def check_status(step, result):
    if result != 0:
        print(f"错误: {step} 失败，请检查网络或权限后重试。")
        sys.exit(1)

# 检查系统资源
def check_system_resources():
    print("检查系统资源...")
    try:
        # 检查磁盘空间（至少需要 1GB 可用）
        stat = os.statvfs(".")
        available_disk = stat.f_bavail * stat.f_frsize // (1024 * 1024)  # MB
        if available_disk < 1024:
            print("错误: 磁盘空间不足（需要至少 1GB 可用），请释放空间后重试。")
            sys.exit(1)
        print(f"磁盘空间充足: {available_disk}MB 可用")

        # 检查内存（至少需要 512MB 可用）
        with open("/proc/meminfo", "r") as f:
            meminfo = f.read()
        available_memory_match = re.search(r"MemAvailable:\s+(\d+)", meminfo)
        if not available_memory_match:
            print("错误: 无法读取可用内存信息。")
            sys.exit(1)
        available_memory = int(available_memory_match.group(1)) // 1024  # MB
        if available_memory < 512:
            print("错误: 可用内存不足（需要至少 512MB 可用），请释放内存后重试。")
            sys.exit(1)
        print(f"可用内存充足: {available_memory}MB")
    except Exception as e:
        print(f"错误: 检查系统资源失败 - {e}")
        sys.exit(1)

# 检查和安装依赖
def check_dependencies():
    print("检查必要依赖...")
    dependencies = ["curl", "tar", "wget", "screen"]
    for cmd in dependencies:
        if shutil.which(cmd) is None:
            print(f"未找到 {cmd}，正在安装...")
            try:
                subprocess.run(["sudo", "apt", "update"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                result = subprocess.run(["sudo", "apt", "install", "-y", cmd], check=True).returncode
                check_status(f"安装 {cmd}", result)
            except subprocess.CalledProcessError as e:
                print(f"错误: 安装 {cmd} 失败 - {e}")
                sys.exit(1)
        else:
            print(f"{cmd} 已安装，跳过。")

# 测试 RPC 是否可用
def test_rpc(rpc_url, chain_name):
    print(f"测试 {chain_name} RPC: {rpc_url} ...")
    headers = {"Content-Type": "application/json"}
    data = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    try:
        response = requests.post(rpc_url, headers=headers, json=data, timeout=5)
        response.raise_for_status()
        if "result" in response.json():
            print(f"{chain_name} RPC 测试通过。")
            return True
    except (requests.RequestException, ValueError):
        pass
    # 备用测试方法：net_version
    data = {"jsonrpc": "2.0", "method": "net_version", "params": [], "id": 1}
    try:
        response = requests.post(rpc_url, headers=headers, json=data, timeout=5)
        response.raise_for_status()
        if "result" in response.json():
            print(f"{chain_name} RPC 测试通过（使用 net_version 方法）。")
            return True
    except (requests.RequestException, ValueError):
        print(f"警告: {chain_name} RPC {rpc_url} 不可用。")
        return False

# 配置 RPC
def configure_rpcs():
    print("检查所需链的 RPC 可用性...")
    default_rpcs = {
        "Arbitrum Sepolia": "https://sepolia-rollup.arbitrum.io/rpc",
        "Base Sepolia": "https://sepolia.base.org",
        "Blast Sepolia": "https://sepolia.blast.io",
        "l2rn": "https://rpc.l2rn.io",
        "Monad Testnet": "https://monad-testnet-rpc.monad.xyz",
        "OP Sepolia": "https://sepolia.optimism.io",
        "Unichain Sepolia": "https://sepolia.unichain.org",
    }
    rpcs = {}
    skipped_chains = []

    for chain, public_rpc in default_rpcs.items():
        if test_rpc(public_rpc, chain):
            rpcs[chain] = public_rpc
        else:
            print(f"{chain} 的公共 RPC 不可用，请提供 Alchemy API 密钥或自定义 RPC URL。")
            alchemy_key = input("选项 1: 输入 Alchemy API 密钥（留空则跳到选项 2）: ").strip()
            if alchemy_key:
                alchemy_urls = {
                    "Arbitrum Sepolia": f"https://arb-sepolia.g.alchemy.com/v2/{alchemy_key}",
                    "Base Sepolia": f"https://base-sepolia.g.alchemy.com/v2/{alchemy_key}",
                    "Blast Sepolia": f"https://blast-sepolia.g.alchemy.com/v2/{alchemy_key}",
                    "l2rn": f"https://l2rn-sepolia.g.alchemy.com/v2/{alchemy_key}",
                    "Monad Testnet": f"https://monad-testnet.g.alchemy.com/v2/{alchemy_key}",
                    "OP Sepolia": f"https://opt-sepolia.g.alchemy.com/v2/{alchemy_key}",
                    "Unichain Sepolia": f"https://unichain-sepolia.g.alchemy.com/v2/{alchemy_key}",
                }
                custom_rpc = alchemy_urls.get(chain)
                if test_rpc(custom_rpc, chain):
                    rpcs[chain] = custom_rpc
                    print(f"{chain} RPC 配置成功: {custom_rpc}")
                    continue
                else:
                    print("错误: 提供的 Alchemy API 密钥生成的 RPC 不可用，请检查密钥或网络。")
            custom_rpc = input(f"选项 2: 输入自定义 {chain} RPC URL（留空则跳过此链）: ").strip()
            if custom_rpc:
                if test_rpc(custom_rpc, chain):
                    rpcs[chain] = custom_rpc
                    print(f"{chain} RPC 配置成功: {custom_rpc}")
                else:
                    print("错误: 提供的自定义 RPC 不可用，请检查 URL 或网络。")
                    sys.exit(1)
            else:
                print(f"跳过 {chain} 的 RPC 配置，可能会影响 Executor 功能。")
                skipped_chains.append(chain)
                rpcs[chain] = ""

    if skipped_chains:
        print("警告: 以下链未配置 RPC，Executor 可能无法处理这些链上的订单：")
        for chain in skipped_chains:
            print(f"- {chain}")
        print("建议至少为关键链（如 Arbitrum Sepolia、OP Sepolia）配置 RPC。")

    print("RPC 配置完成:")
    for chain, rpc in rpcs.items():
        print(f"{chain}: {rpc}")
    return rpcs

# 配置环境变量
def configure_env():
    print("配置 t3rn Executor 环境变量...")
    private_key = getpass.getpass("请提供您的钱包私钥（用于 Executor 操作，输入不会显示）: ")
    if not private_key:
        print("错误: 私钥不能为空。")
        sys.exit(1)

    rpcs = configure_rpcs()

    env_content = [
        "EXECUTOR_PROCESS_BIDS_ENABLED=true",
        "EXECUTOR_PROCESS_ORDERS_ENABLED=true",
        "EXECUTOR_PROCESS_CLAIMS_ENABLED=true",
        f"EXECUTOR_PRIVATE_KEY=\"{private_key}\"",
        "LOG_LEVEL=info",
        "LOG_PRETTY=true",
    ]

    rpc_json = json.dumps({chain: rpc for chain, rpc in rpcs.items() if rpc})
    env_content.append(f"EXECUTOR_RPC_URLS='{rpc_json}'")

    # 可选配置
    options = [
        ("EXECUTOR_MAX_BID_AMOUNT", "设置每次竞标的最大金额（默认: 1000）", 1000),
        ("EXECUTOR_MIN_ORDER_VALUE", "设置处理订单的最小价值（默认: 10）", 10),
        ("EXECUTOR_CONCURRENT_REQUESTS", "设置并行处理的请求数（默认: 5）", 5),
        ("EXECUTOR_GAS_LIMIT", "设置每次交易的Gas上限（默认: 200000）", 200000),
    ]
    for key, desc, default in options:
        print(f"\n{desc}")
        choice = input(f"是否自定义此值？(y/n，默认 {default}): ").strip().lower()
        if choice == "y":
            value = input(f"请输入值（整数，例如 {default * 2}）: ").strip()
            if not value.isdigit():
                print("错误: 请输入有效的整数。")
                sys.exit(1)
            env_content.append(f"{key}={value}")
        else:
            env_content.append(f"{key}={default}")

    try:
        with open(".env", "w") as f:
            f.write("\n".join(env_content))
        os.chmod(".env", 0o600)
        print("环境变量配置完成，写入到 .env 文件。")
        print("注意: .env 文件包含敏感信息（如私钥），已设置为仅当前用户可读写，请妥善保管。")
    except Exception as e:
        print(f"错误: 写入环境变量失败 - {e}")
        sys.exit(1)

# 一键部署 t3rn Executor
def deploy_executor():
    print("开始部署 t3rn Executor...")
    check_system_resources()
    check_dependencies()

    try:
        if not os.path.exists("t3rn"):
            os.mkdir("t3rn")
        os.chdir("t3rn")
    except Exception as e:
        print(f"错误: 创建或进入 t3rn 目录失败 - {e}")
        sys.exit(1)

    print("获取最新 Executor 版本...")
    try:
        response = requests.get("https://api.github.com/repos/t3rn/executor-release/releases/latest", timeout=10)
        response.raise_for_status()
        latest_version = response.json()["tag_name"]
        print(f"最新版本: {latest_version}")
    except (requests.RequestException, ValueError) as e:
        print(f"错误: 无法获取最新版本，请检查网络连接 - {e}")
        sys.exit(1)

    executor_url = f"https://github.com/t3rn/executor-release/releases/download/{latest_version}/executor-linux-{latest_version}.tar.gz"
    print("下载 Executor 二进制文件...")
    try:
        subprocess.run(["curl", "-LO", executor_url], check=True)
        print("解压文件...")
        subprocess.run(["tar", "-xzf", f"executor-linux-{latest_version}.tar.gz"], check=True)
        os.remove(f"executor-linux-{latest_version}.tar.gz")
    except subprocess.CalledProcessError as e:
        print(f"错误: 下载或解压 Executor 文件失败 - {e}")
        sys.exit(1)

    try:
        os.chdir("executor/executor/bin")
    except Exception as e:
        print(f"错误: 进入 bin 目录失败 - {e}")
        sys.exit(1)

    configure_env()

    executor_path = "./executor"
    if not os.access(executor_path, os.X_OK):
        os.chmod(executor_path, 0o755)

    # 检查 screen 会话
    screen_list = subprocess.run(["screen", "-list"], capture_output=True, text=True)
    if "t3rn-executor" in screen_list.stdout:
        print("警告: 检测到已有 t3rn-executor 的 screen 会话正在运行！")
        print("请先使用 'screen -r t3rn-executor' 检查，或手动终止后再部署。")
        confirm = input("是否继续部署新实例？(y/n): ").strip().lower()
        if confirm != "y":
            print("取消部署，返回主菜单。")
            return
        subprocess.run(["screen", "-S", "t3rn-executor", "-X", "quit"])

    print("在 screen 会话中启动 t3rn Executor...")
    try:
        with open("executor.log", "a") as log:
            subprocess.Popen(
                ["screen", "-dmS", "t3rn-executor", "bash", "-c", f"source .env && {executor_path}"],
                stdout=log,
                stderr=log
            )
        time.sleep(2)
        screen_check = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        if "t3rn-executor" in screen_check.stdout:
            print("t3rn Executor 部署并启动成功！")
            print("日志输出到 t3rn/executor/executor/bin/executor.log")
            print("提示: 使用 'screen -r t3rn-executor' 查看运行中的 Executor。")
        else:
            print("错误: Executor 启动失败，请查看 executor.log 检查问题。")
            sys.exit(1)
    except Exception as e:
        print(f"错误: 启动 Executor 失败 - {e}")
        sys.exit(1)

# 查看最新日志
def view_latest_logs():
    log_file = "t3rn/executor/executor/bin/executor.log"
    if os.path.exists(log_file):
        print("显示最近 50 行日志（按 Ctrl+C 退出查看）:")
        try:
            subprocess.run(["tail", "-n", "50", "-f", log_file])
        except KeyboardInterrupt:
            print("\n已停止查看日志。")
    else:
        print(f"错误: 日志文件 {log_file} 不存在，请先部署 Executor。")

# 查看订单数量（近一小时）
def view_order_stats():
    log_file = "t3rn/executor/executor/bin/executor.log"
    if not os.path.exists(log_file):
        print(f"错误: 日志文件 {log_file} 不存在，请先部署 Executor。")
        return

    print("统计近一小时的订单数量...")
    one_hour_ago = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    print(f"统计时间范围: 从 {one_hour_ago} 到现在 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

    try:
        with open(log_file, "r") as f, tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            for line in f:
                if re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", line) and line >= f"[{one_hour_ago}]":
                    temp.write(line)
            temp_file = temp.name

        completed = 0
        pending = []
        with open(temp_file, "r") as f:
            lines = f.readlines()
            completed = sum(1 for line in lines if '"status":"completed"' in line)
            pending = [line for line in lines if '"status":"pending"' in line or '"status":"failed"' in line]

        print(f"近一小时已完成订单数量: {completed}")
        print("近一小时未完成订单数量及原因:")
        print(f"未完成订单总数: {len(pending)}")
        if pending:
            print("未完成订单详情:")
            for line in pending:
                order_id_match = re.search(r'"order_id":"([^"]*)"', line)
                reason_match = re.search(r'"reason":"([^"]*)"', line)
                order_id = order_id_match.group(1) if order_id_match else "未知"
                reason = reason_match.group(1) if reason_match else "未知原因（日志中未提供具体原因）"
                print(f"订单 ID: {order_id}, 状态: 未完成, 原因: {reason}")

        os.remove(temp_file)
    except Exception as e:
        print(f"错误: 统计订单数量失败 - {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

# 查看日志子菜单
def view_logs():
    while True:
        print("====================================")
        print("查看日志选项")
        print("1. 查看最新日志")
        print("2. 查看近一小时订单数量")
        print("0. 返回主菜单")
        choice = input("请选择操作 (输入数字): ").strip()

        if choice == "1":
            view_latest_logs()
        elif choice == "2":
            view_order_stats()
        elif choice == "0":
            print("返回主菜单...")
            return
        else:
            print("无效选项，请输入 0、1 或 2。")

# 提示用户如何恢复 screen
def show_screen_help():
    print("提示: 如果 Executor 正在运行，您可以使用以下命令恢复 screen 会话：")
    print("  screen -r t3rn-executor")
    print("在 screen 中，按 Ctrl+C 可停止 Executor，按 Ctrl+A 后按 D 可脱离 screen。")
    print("若要查看所有 screen 会话，运行：screen -list")

# 主菜单循环
def main():
    while True:
        print("====================================")
        print("t3rn Executor 交互式脚本 - Ubuntu 22.04")
        print(f"当前日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("====================================")
        print("1. 一键部署 t3rn Executor")
        print("2. 查看 Executor 日志")
        print("0. 退出脚本")
        choice = input("请选择操作 (输入数字): ").strip()

        if choice == "1":
            deploy_executor()
            show_screen_help()
        elif choice == "2":
            view_logs()
        elif choice == "0":
            print("退出脚本，谢谢使用！")
            show_screen_help()
            sys.exit(0)
        else:
            print("无效选项，请输入 0、1 或 2。")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户中断脚本，退出。")
        show_screen_help()
        sys.exit(0)
    except Exception as e:
        print(f"错误: 脚本执行过程中发生未知错误 - {e}")
        sys.exit(1)