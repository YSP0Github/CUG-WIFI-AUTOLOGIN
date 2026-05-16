# CUG Auto Login

中国地质大学（CUG）校园网自动重连程序。检测到断网时自动完成 WiFi 连接和校园网认证登录，并通过邮件通知。

## 功能

- **网络状态检测** — 定时检查是否联网，有网时直接跳过
- **WiFi 自动重连** — 断开时自动连接指定的 CUG WiFi
- **Clash 代理应急** — 检测到系统代理开启时，临时关闭代理再尝试重连，完成后自动恢复
- **校园网自动登录** — 通过 Selenium 操作 Edge 浏览器完成认证登录
- **邮件通知** — 登录成功后发送邮件，附带本次运行日志
- **进程锁** — PID 锁机制防止多实例重复运行

## 环境要求

- Windows 10/11
- Python 3.9+
- Microsoft Edge 浏览器

## 安装

### 1. 安装 Python 依赖

```bash
pip install selenium requests
```

### 2. 下载 Edge WebDriver

查看你的 Edge 浏览器版本（地址栏输入 `edge://version`），然后从 [npmmirror](https://npmmirror.com/mirrors/edgedriver/) 下载对应版本的 `msedgedriver_win64.zip`，解压到项目目录的 `edgedriver/` 文件夹下：

```
edgedriver/
└── msedgedriver.exe
```

### 3. 配置

复制 `config.ini.example` 为 `config.ini`，填入你的信息：

```ini
[credentials]
USERNAME = 你的学号
PASSWORD = 你的密码

[email]
EMAIL_SENDER = 你的邮箱@qq.com
EMAIL_PASSWORD = QQ邮箱SMTP授权码
EMAIL_RECEIVER = 收件邮箱@qq.com

[browser]
DRIVER_PATH = ./edgedriver/msedgedriver.exe

[wifi]
SSID = CUG
```

> `EMAIL_PASSWORD` 是 QQ 邮箱的 **SMTP 授权码**，不是 QQ 密码。在 QQ 邮箱设置 > 账户 > POP3/SMTP 服务中开启并获取。

## 使用方式

### 手动运行

```bash
python Login_CUG.py
```

### 定时任务（推荐）

以管理员身份运行 `setup_task.bat`，会创建 Windows 任务计划，每 30 分钟自动检测一次网络。

管理命令：

```bash
# 查看任务
schtasks /query /tn CUG_AutoReconnect

# 手动触发
schtasks /run /tn CUG_AutoReconnect

# 删除任务
schtasks /delete /tn CUG_AutoReconnect /f
```

## 运行流程

```
检测联网状态
  ├─ 已联网 → 退出
  └─ 未联网
       ├─ 检查 WiFi → 未连接则尝试连接 CUG
       ├─ 关闭系统代理 → 网络恢复则恢复代理并退出
       └─ 启动 Edge → 登录校园网 → 发送邮件通知
```

## 项目结构

```
CUG_AUTO_LOGIN/
├── Login_CUG.py          # 主程序
├── config.ini            # 配置文件（需自行创建）
├── setup_task.bat        # 创建 Windows 定时任务
├── edgedriver/           # Edge WebDriver（需自行下载）
│   └── msedgedriver.exe
├── logs/                 # 运行日志（自动生成）
│   ├── general_log.txt
│   └── log_*.txt
└── README.md
```

## 常见问题

**Q: Edge 更新后无法启动浏览器？**
A: Edge 版本更新后需要重新下载对应版本的 `msedgedriver.exe` 替换到 `edgeddriver/` 目录。

**Q: 关了 Clash 代理才能连上校园网？**
A: 程序已内置代理应急方案，检测到代理开启时会自动关闭 → 尝试重连 → 成功后恢复代理。

**Q: 邮件发送失败？**
A: 确认 `config.ini` 中的邮箱配置正确，且 `EMAIL_PASSWORD` 使用的是 QQ 邮箱 SMTP 授权码。注意 `config.ini` 中不要使用行内注释（`#`）。
