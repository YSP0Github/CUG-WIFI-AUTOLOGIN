# CUG Auto Login

中国地质大学（CUG）校园网自动重连程序。检测到断网时自动完成 WiFi 连接和校园网认证登录，并通过邮件通知。

## 应用场景

- **远程桌面/SSH** — 电脑放在实验室或宿舍，通过远程连接操作时网络突然断开，程序自动重连，避免失联
- **长时间挂机下载** — 晚上挂任务时校园网掉线，程序自动恢复，第二天醒来任务已完成
- **出差/外出** — 人在外地，电脑留在学校，校园网掉了也能自动重连，随时远程访问
- **多设备管理** — 多台电脑部署后各自独立运行，统一通过邮件获知重连状态
- **代理环境** — 使用 Clash 等代理工具时，校园网认证会被代理干扰，程序自动处理代理切换

## 功能

- **网络状态检测** — 定时检查是否联网，有网时直接跳过
- **WiFi 自动重连** — 断开时自动连接指定的校园 WiFi
- **Clash 代理应急** — 检测到系统代理开启时，临时关闭代理再尝试重连，完成后自动恢复
- **校园网自动登录** — 通过 Selenium 操作 Edge 浏览器完成认证登录
- **邮件通知** — 登录成功后发送邮件，附带本次运行日志
- **进程锁** — PID 锁机制防止多实例重复运行

## 平台兼容性

| 平台 | 状态 |
|------|------|
| Windows 10/11 | 已测试，正常运行 |
| macOS | 未测试，部分功能可能需要修改（系统代理控制、WiFi 连接命令等） |
| Linux | 未测试，部分功能可能需要修改 |

> 本程序目前仅在 **Windows** 上测试通过。`winreg`（注册表操作）和 `netsh wlan`（WiFi 管理）是 Windows 特有的 API，macOS/Linux 如需使用需要自行适配相关部分。

## 其他学校能否使用？

可以，但需要根据你的校园网认证页面修改代码中的以下部分：

1. **认证页面地址** — [Login_CUG.py](Login_CUG.py) 中 `check_page_status()` 里的 URL
2. **页面元素** — `check_page_status()`、`logout_and_refresh()`、`login()` 中的元素 ID 和 XPath
3. **WiFi 名称** — `config.ini` 中的 `SSID`

核心的网络检测、代理控制、邮件通知、定时任务等逻辑是通用的，不需要改动。

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

**复制 `config.ini.example` 为 `config.ini`**，然后用记事本打开，填入你自己的信息。

> **重要**: `config.ini` 中 **不要使用行内注释**（`#` 号），否则会导致读取配置异常。注释请单独写一行。

```ini
[credentials]
# 校园网登录的学号和密码
USERNAME = 你的学号
PASSWORD = 你的密码

[email]
# 发件人和收件人邮箱（发件人需要开启 SMTP 服务）
EMAIL_SENDER = 你的邮箱@qq.com
# 注意：这里填的是 SMTP 授权码，不是 QQ 密码！
EMAIL_PASSWORD = 你的SMTP授权码
EMAIL_RECEIVER = 收件邮箱@qq.com

[browser]
# Edge WebDriver 路径，根据你的实际位置修改
DRIVER_PATH = ./edgedriver/msedgedriver.exe

[wifi]
# 校园 WiFi 名称
SSID = CUG
```

### 如何获取 QQ 邮箱 SMTP 授权码？

1. 登录 [QQ 邮箱](https://mail.qq.com/)
2. 点击 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务**
4. 开启 **POP3/SMTP 服务**（需要绑定手机号验证）
5. 开启成功后会生成一个 **授权码**，复制填入 `config.ini` 的 `EMAIL_PASSWORD`

> 如果你用的不是 QQ 邮箱，需要修改代码中 `smtplib.SMTP("smtp.qq.com", 587)` 为对应邮箱的 SMTP 服务器地址。

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
       ├─ 检查 WiFi → 未连接则尝试连接校园网
       ├─ 关闭系统代理 → 网络恢复则恢复代理并退出
       └─ 启动 Edge → 登录校园网 → 发送邮件通知
```

## 项目结构

```
CUG_AUTO_LOGIN/
├── Login_CUG.py          # 主程序
├── config.ini.example    # 配置模板（复制为 config.ini 后填入你的信息）
├── config.ini            # 你的配置文件（不会上传到 GitHub）
├── setup_task.bat        # 创建 Windows 定时任务
├── edgedriver/           # Edge WebDriver（需自行下载）
│   └── msedgedriver.exe
├── logs/                 # 运行日志（自动生成，不会上传）
│   ├── general_log.txt
│   └── log_*.txt
└── README.md
```

## 常见问题

**Q: Edge 更新后无法启动浏览器？**
A: Edge 版本更新后需要重新下载对应版本的 `msedgedriver.exe` 替换到 `edgedriver/` 目录。

**Q: 关了 Clash 代理才能连上校园网？**
A: 程序已内置代理应急方案，检测到代理开启时会自动关闭 → 尝试重连 → 成功后恢复代理。

**Q: 邮件发送失败？**
A: 确认 `config.ini` 中的邮箱配置正确，且 `EMAIL_PASSWORD` 使用的是 QQ 邮箱 SMTP **授权码**（不是 QQ 密码）。另外注意 `config.ini` 中不要使用行内注释（`#`）。

**Q: config.ini 怎么配置？**
A: 复制 `config.ini.example` 为 `config.ini`，用记事本打开后填入学号、密码、邮箱信息即可。详见上方「配置」章节。

**Q: 程序运行后没有反应？**
A: 可能是当前已联网，程序检测到网络正常后会直接退出。可以在断网状态下运行来测试。

**Q: 怎么确认定时任务在正常运行？**
A: 查看 `logs/` 目录下的日志文件。每次程序运行都会记录，如果长时间没有新日志，检查任务计划程序中的任务状态。
