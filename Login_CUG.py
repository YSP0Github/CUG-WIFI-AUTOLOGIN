"""
CUG 校园网自动重连程序
=====================
检测到断网时自动连接 WiFi → 登录校园网 → 发送邮件通知
适用于 Windows + Clash 代理环境

使用方法:
  1. 复制 config.ini.example 为 config.ini，填入你的信息
  2. 下载 Edge WebDriver 放到 edgedriver/ 目录
  3. 运行: python Login_CUG.py
  4. 或以管理员身份运行 setup_task.bat 创建定时任务
"""

import os
import sys
import time
import smtplib
import configparser
import requests
import winreg
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime


# ============================================================
# 配置文件读取
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.ini")

# 检查 config.ini 是否存在
if not os.path.isfile(CONFIG_FILE):
    print("=" * 50)
    print("  错误: 找不到 config.ini 配置文件！")
    print("=" * 50)
    print()
    print("  请按以下步骤操作:")
    print("  1. 复制 config.ini.example 为 config.ini")
    print("  2. 用记事本打开 config.ini")
    print("  3. 填入你的学号、密码、邮箱等信息")
    print()
    print("  注意: config.ini 中不要使用行内注释(中文 # 号)")
    print("=" * 50)
    input("按回车键退出...")
    sys.exit(1)

config = configparser.ConfigParser()
config.read(CONFIG_FILE, encoding="utf-8")

# 读取配置项，缺失时给出友好提示
def get_config(section, key, fallback=None):
    """安全读取配置，缺失时打印提示"""
    try:
        value = config.get(section, key, fallback=fallback)
        if not value or value.strip() == "":
            print(f"[警告] config.ini 中 [{section}] {key} 为空，请检查配置")
            return fallback
        return value
    except (configparser.NoSectionError, configparser.NoOptionError):
        print(f"[警告] config.ini 中缺少 [{section}] {key}，请检查配置")
        return fallback

USERNAME = get_config("credentials", "USERNAME")
PASSWORD = get_config("credentials", "PASSWORD")
EMAIL_SENDER = get_config("email", "EMAIL_SENDER")
EMAIL_PASSWORD = get_config("email", "EMAIL_PASSWORD")
EMAIL_RECEIVER = get_config("email", "EMAIL_RECEIVER")
SSID = get_config("wifi", "SSID", fallback="CUG")

# 启动前校验关键配置
_config_errors = []
if not USERNAME or not PASSWORD:
    _config_errors.append("学号或密码未配置 ([credentials] USERNAME / PASSWORD)")
if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
    _config_errors.append("邮箱配置不完整 ([email] 部分)")

if _config_errors:
    print("=" * 50)
    print("  错误: config.ini 配置不完整！")
    print("=" * 50)
    for err in _config_errors:
        print(f"  - {err}")
    print()
    print("  请打开 config.ini 补充完整后重试")
    print("=" * 50)
    input("按回车键退出...")
    sys.exit(1)


# ============================================================
# 日志系统
# ============================================================

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
GENERAL_LOG_FILE = os.path.join(LOG_DIR, "general_log.txt")
DATE_LOG_FILE = os.path.join(LOG_DIR, f"log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt")


def write_log(message, log_file=None):
    """写入日志到文件和控制台"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    if not log_file:
        # 同时写入累计日志和本次日志
        with open(GENERAL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        with open(DATE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    else:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line)
    print(message)


# ============================================================
# 系统代理控制 (Clash 等代理工具的应急备案)
# 通过修改 Windows 注册表的 ProxyEnable 来开关系统代理
# ============================================================

INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def get_proxy_enabled():
    """读取当前系统代理是否开启"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "ProxyEnable")
        winreg.CloseKey(key)
        return bool(value)
    except OSError:
        return False


def set_proxy_enabled(enabled):
    """设置系统代理开/关 (True=开启, False=关闭)"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enabled else 0)
        winreg.CloseKey(key)
        write_log(f"系统代理已{'开启' if enabled else '关闭'}")
        return True
    except OSError as e:
        write_log(f"设置系统代理失败: {e}")
        return False


def disable_proxy():
    """关闭系统代理"""
    return set_proxy_enabled(False)


def enable_proxy():
    """开启系统代理"""
    return set_proxy_enabled(True)


# ============================================================
# 网络检测与 WiFi 连接
# ============================================================

def is_connected():
    """检测是否能访问外网 (通过访问百度判断)"""
    try:
        response = requests.get("https://www.baidu.com", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def check_wifi_connection():
    """检查当前是否连接了 WiFi (不要求特定 SSID)"""
    try:
        result = os.popen("netsh wlan show interfaces").read()
        if "SSID" not in result:
            write_log("当前未连接任何 WiFi")
            return False
        else:
            write_log("已连接 WiFi")
            return True
    except Exception as e:
        write_log(f"检查 WiFi 状态时出错: {e}")
        return False


def connect_to_wifi(ssid, password=None):
    """尝试连接指定的 WiFi 网络"""
    try:
        command = f'netsh wlan connect name="{ssid}"'
        if password:
            command += f' key="{password}"'
        os.system(command)
        time.sleep(5)  # 等待连接建立
        write_log(f"尝试连接 WiFi: {ssid}")
        if is_connected():
            write_log("WiFi 连接成功，网络已恢复")
            return True
        else:
            write_log("WiFi 连接后仍无法上网")
            return False
    except Exception as e:
        write_log(f"连接 WiFi 时出错: {e}")
        return False


# ============================================================
# 浏览器自动化 (Selenium + Edge)
# ============================================================

def setup_browser():
    """
    初始化 Edge 浏览器 (无头模式)
    优先使用 config.ini 中配置的本地驱动路径
    """
    options = webdriver.EdgeOptions()
    options.add_argument("--headless")    # 无界面模式，后台运行
    options.add_argument("--disable-gpu") # 禁用 GPU 加速，避免兼容问题

    # 优先使用 config 中配置的本地驱动路径 (断网时可用)
    driver_path = config.get("browser", "DRIVER_PATH", fallback=None)
    if driver_path and os.path.isfile(driver_path):
        service = Service(driver_path)
        return webdriver.Edge(service=service, options=options)

    # 未配置本地驱动时，尝试 Selenium 自动管理 (需要联网下载)
    try:
        return webdriver.Edge(options=options)
    except Exception as e:
        write_log(f"启动浏览器失败: {e}")
        write_log("提示: 请下载 Edge WebDriver 放到 edgedriver/ 目录")
        write_log("下载地址: https://npmmirror.com/mirrors/edgedriver/")
        raise


def check_page_status(driver):
    """
    打开校园网认证页面，判断当前状态:
      - "logged_in":   已登录 (有注销按钮)
      - "not_logged_in": 未登录 (有登录按钮)
      - "unknown":      无法判断
    """
    url = "http://192.168.167.115/srun_portal_success?ac_id=1&theme=pro"
    driver.get(url)
    time.sleep(2)

    try:
        logout_button = driver.find_element(By.ID, "logout")
        if logout_button.is_displayed():
            return "logged_in"
    except Exception:
        pass

    try:
        login_button = driver.find_element(By.XPATH, "//button[text()='登录']")
        if login_button.is_displayed():
            return "not_logged_in"
    except Exception:
        pass

    return "unknown"


def logout_and_refresh(driver):
    """注销当前登录并刷新页面，为重新登录做准备"""
    try:
        logout_button = driver.find_element(By.ID, "logout")
        logout_button.click()
        time.sleep(1)

        confirm_button = driver.find_element(By.XPATH, "//button[text()='确认']")
        confirm_button.click()

        time.sleep(3)
        driver.refresh()
        write_log("已注销并刷新页面", log_file=DATE_LOG_FILE)
    except Exception as e:
        write_log(f"注销时出错: {e}", log_file=DATE_LOG_FILE)


def login(driver, username, password):
    """在校园网认证页面填写账号密码并登录"""
    try:
        if not username or not password:
            write_log("用户名或密码为空，无法登录", log_file=DATE_LOG_FILE)
            return

        # 等待用户名输入框加载完成
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )

        # 填写用户名
        username_field = driver.find_element(By.ID, "username")
        username_field.clear()
        username_field.send_keys(username)

        # 填写密码
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(password)

        # 点击登录按钮
        login_button = driver.find_element(By.XPATH, "//button[text()='登录']")
        login_button.click()

        time.sleep(3)
        driver.refresh()
        write_log("登录成功并刷新页面", log_file=DATE_LOG_FILE)
    except Exception as e:
        write_log(f"登录时出错: {e}", log_file=DATE_LOG_FILE)


# ============================================================
# 邮件通知
# ============================================================

def send_email(subject, body, attachment=None):
    """
    发送邮件通知 (通过 QQ 邮箱 SMTP)
    成功登录校园网后调用，附带本次运行日志
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.set_charset("utf-8")

        # 构建邮件正文
        full_body = body
        if attachment and os.path.isfile(attachment):
            with open(attachment, "r", encoding="utf-8") as f:
                attachment_content = f.read()
                full_body += "\n\n--- Log ---\n" + attachment_content

        msg.attach(MIMEText(full_body, "plain", "utf-8"))

        # 添加日志文件作为附件
        if attachment and os.path.isfile(attachment):
            with open(attachment, "rb") as f:
                attach = MIMEText(f.read(), "base64", "utf-8")
                attach["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment)}"'
                msg.attach(attach)

        # 连接 SMTP 服务器并发送
        server = smtplib.SMTP("smtp.qq.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()

        write_log("邮件发送成功")
    except Exception as e:
        write_log(f"邮件发送失败: {e}")


# ============================================================
# 主程序
# ============================================================

def main():
    """
    主流程:
    1. 检测是否联网 → 已联网则跳过
    2. 检查 WiFi 连接 → 未连接则尝试连接
    3. 检查系统代理 → 代理开启则关闭后重试
    4. 启动浏览器登录校园网 → 发送邮件通知
    """
    write_log("===== 程序启动 =====")

    # 第一步: 检测联网状态
    if is_connected():
        write_log("当前已联网，无需操作")
        return

    write_log("检测到断网，开始重连流程...")

    # 第二步: 检查 WiFi 连接
    if not check_wifi_connection():
        write_log(f"未连接 WiFi，尝试连接 {SSID}...")
        if not connect_to_wifi(SSID):
            write_log(f"无法连接 {SSID}，请检查网络环境或 WiFi 密码")
            return

    # 连上 WiFi 后再次检测是否能上网
    if is_connected():
        write_log("网络已恢复")
        return

    # 第三步: 应急备案 — 关闭 Clash 系统代理
    # 校园网认证走内网 (192.168.x.x)，代理会干扰连接
    proxy_was_on = get_proxy_enabled()
    if proxy_was_on:
        write_log("检测到系统代理已开启，尝试关闭代理后重连...")
        disable_proxy()
        time.sleep(2)

        # 关闭代理后再次检测
        if is_connected():
            write_log("关闭代理后网络已恢复，跳过校园网登录")
            enable_proxy()  # 恢复代理
            return

    # 第四步: 启动浏览器登录校园网
    write_log("尝试启动浏览器并登录校园网...")
    driver = setup_browser()
    try:
        page_status = check_page_status(driver)

        if page_status == "logged_in":
            # 已登录但没网 → 注销后重新登录
            write_log("检测到已登录状态，先注销再重新登录...")
            logout_and_refresh(driver)
            login(driver, USERNAME, PASSWORD)
            send_email(
                "CUG WiFi Reconnected",
                "Network was down. Successfully re-logged in to campus WiFi.",
                attachment=DATE_LOG_FILE
            )

        elif page_status == "not_logged_in":
            # 未登录 → 直接登录
            write_log("检测到未登录状态，开始登录...")
            login(driver, USERNAME, PASSWORD)
            send_email(
                "CUG WiFi Login Success",
                "Network was down. Successfully logged in to campus WiFi.",
                attachment=DATE_LOG_FILE
            )
        else:
            write_log("无法确定页面状态，请手动检查校园网页面")

    except Exception as e:
        write_log(f"程序执行出错: {e}")

    finally:
        time.sleep(5)
        driver.quit()

        # 无论成功与否，都恢复系统代理
        if proxy_was_on:
            enable_proxy()

        write_log("===== 程序结束 =====\n")


# ============================================================
# 入口: 防重复运行 + 启动主程序
# ============================================================

if __name__ == "__main__":
    LOCK_FILE = os.path.join(LOG_DIR, ".lock")

    def is_process_running(pid):
        """检查指定 PID 的进程是否仍在运行"""
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False

    # 检查是否有残留的锁文件 (上次异常退出留下的)
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if is_process_running(old_pid):
                print(f"另一个实例 (PID {old_pid}) 正在运行，跳过本次执行")
                sys.exit(0)
            else:
                print(f"清理残留锁文件 (旧 PID {old_pid})")
                os.remove(LOCK_FILE)
        except (ValueError, OSError):
            os.remove(LOCK_FILE)

    # 写入当前 PID 到锁文件，启动主程序
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        main()
    except Exception as e:
        print(f"程序异常退出: {e}")
    finally:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass
