#!/bin/bash

# 批量下载3RScan数据的Shell脚本
# 使用sudo权限和指定的Python环境来执行download_3RScan.py脚本
# 遍历scans.txt文件中的每个ID，将其作为--id参数传入
# 对于已存在的文件夹自动跳过

# 配置参数
download_script="download_3RScan.py"
scans_file="scans.txt"
download_dir="/mnt/intel1.7/ktj/Retrieval/3RScan"
python_env="/home/kangtengjia/miniconda3/envs/crossover/bin/python"
log_dir="./logs"
start_idx=0
end_idx=2000

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo "选项:"
    echo "  --scans_file <文件路径>   包含scan IDs的文件路径，默认为scans.txt"
    echo "  --download_dir <目录路径> 下载目录，默认为/mnt/intel1.7/ktj/Retrieval/3RScan"
    echo "  --python_env <Python路径> 指定Python环境路径，默认为~/miniconda3/envs/crossover/bin/python"
    echo "  --log_dir <目录路径>      日志文件保存目录，默认为./logs"
    echo "  --start_idx <索引>       开始下载的索引位置，默认为0"
    echo "  --end_idx <索引>         结束下载的索引位置，默认为-1（文件末尾）"
    echo "  --help                   显示此帮助信息"
    exit 1
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --scans_file)
            scans_file="$2"
            shift 2
            ;;
        --download_dir)
            download_dir="$2"
            shift 2
            ;;
        --python_env)
            python_env="$2"
            shift 2
            ;;
        --log_dir)
            log_dir="$2"
            shift 2
            ;;
        --start_idx)
            start_idx="$2"
            shift 2
            ;;
        --end_idx)
            end_idx="$2"
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            echo "未知选项: $1"
            show_help
            ;;
    esac
done

# 确保日志目录存在
mkdir -p "$log_dir"

# 生成带时间戳的日志文件名
timestamp=$(date +"%Y%m%d_%H%M%S")
log_file="$log_dir/batch_download_sudo_$timestamp.log"

# 检查必要文件是否存在
if [ ! -f "$scans_file" ]; then
    echo "错误: 找不到scans文件 $scans_file" | tee -a "$log_file"
    exit 1
fi

if [ ! -f "$download_script" ]; then
    echo "错误: 找不到下载脚本 $download_script" | tee -a "$log_file"
    exit 1
fi

# 确保下载目录存在
sudo mkdir -p "$download_dir" 2>> "$log_file"

# 初始化日志文件
echo "===== 批量下载任务开始于 $(date) =====" | tee -a "$log_file"
echo "配置参数:" | tee -a "$log_file"
echo "  scans_file: $scans_file" | tee -a "$log_file"
echo "  download_dir: $download_dir" | tee -a "$log_file"
echo "  python_env: $python_env" | tee -a "$log_file"
echo "  log_dir: $log_dir" | tee -a "$log_file"
echo "  log_file: $log_file" | tee -a "$log_file"
echo "  start_idx: $start_idx" | tee -a "$log_file"
echo "  end_idx: $end_idx" | tee -a "$log_file"

# 读取scans.txt文件中的所有ID并进行处理
echo "开始处理scan IDs..." | tee -a "$log_file"

# 处理索引范围
if [ "$end_idx" -eq -1 ]; then
    # 如果end_idx为-1，则读取从start_idx到文件末尾的所有行
    scan_ids=$(sed -n "$((start_idx+1))p" "$scans_file")
else
    # 否则读取从start_idx到end_idx的行
    scan_ids=$(sed -n "$((start_idx+1)),${end_idx}p" "$scans_file")
fi

# 统计要处理的ID数量
total_ids=$(echo "$scan_ids" | wc -l)
echo "找到 $total_ids 个scan IDs 需要处理" | tee -a "$log_file"

success_count=0
failed_count=0
skip_count=0
start_time=$(date +%s)

# 遍历每个ID
echo "开始下载..." | tee -a "$log_file"
i=0
while read -r scan_id; do
    # 跳过空行
    if [ -z "$scan_id" ]; then
        continue
    fi
    
    i=$((i+1))
    echo "进度: $i/$total_ids - 处理scan ID: $scan_id" | tee -a "$log_file"
    
    # 检查是否已下载（存在同id名文件夹）
    scan_dir="$download_dir/$scan_id"
    if [ -d "$scan_dir" ]; then
        echo "  已存在，跳过下载" | tee -a "$log_file"
        skip_count=$((skip_count+1))
        continue
    fi
    
    # 构建下载命令
    cmd="sudo $python_env $download_script -o $download_dir --id $scan_id"
    echo "  执行命令: $cmd" | tee -a "$log_file"
    
    # 执行下载命令
    start_scan_time=$(date +%s)
    $cmd >> "$log_file" 2>&1
    result=$?
    end_scan_time=$(date +%s)
    duration=$((end_scan_time - start_scan_time))
    
    # 检查命令执行结果
    if [ $result -eq 0 ]; then
        echo "  成功下载，耗时: $duration秒" | tee -a "$log_file"
        success_count=$((success_count+1))
    else
        echo "  下载失败! 错误码: $result" | tee -a "$log_file"
        failed_count=$((failed_count+1))
    fi
done <<< "$scan_ids"

# 计算总耗时
end_time=$(date +%s)
total_duration=$((end_time - start_time))

# 输出统计信息
stats="\n===== 批量下载任务完成于 $(date) =====\n"
stats+="总数量: $total_ids\n"
stats+="成功下载: $success_count\n"
stats+="已存在跳过: $skip_count\n"
stats+="下载失败: $failed_count\n"
stats+="总耗时: $total_duration秒\n"

echo -e "$stats" | tee -a "$log_file"

echo "日志文件已保存到: $log_file"