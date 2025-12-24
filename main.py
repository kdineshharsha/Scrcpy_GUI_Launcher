import sys
import os
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QLabel,
)
from PySide6.QtGui import QAction
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile
import subprocess
from datetime import datetime
import re


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def tool_path(name):
    base_dir = (
        os.path.dirname(sys.executable)
        if getattr(sys, "frozen", False)
        else os.path.abspath(".")
    )
    return os.path.join(base_dir, "tools", name)


app = QApplication(sys.argv)
file = QFile(resource_path("main.ui"))
file.open(QFile.ReadOnly)

loader = QUiLoader()
window = loader.load(file)

file.close()

# ---------------- ACCESS WIDGETS ----------------
startBtn = window.findChild(QPushButton, "startBtn")
recordBtn = window.findChild(QPushButton, "recordBtn")
searchInput = window.findChild(QLineEdit, "searchInput")
appList = window.findChild(QListWidget, "appList")
manualAction = window.findChild(QAction, "actionManual_Connect")
autoAction = window.findChild(QAction, "actionAutomatic_Connect")
helpAction = window.findChild(QAction, "actionHelp")
aboutAction = window.findChild(QAction, "actionAbout")
device = window.findChild(QLabel, "txtDevice")
status = window.findChild(QLabel, "txtStatus")
# ---------------- TEST CONNECTIONS ----------------

all_apps = []


def on_start_clicked():
    item = appList.currentItem()
    if not item:
        QMessageBox.information(
            window, "No Selection", "Please select an app from the list."
        )
        return
    package_name = item.text()

    command = [tool_path("scrcpy.exe"), "--new-display", "--start-app", package_name]

    try:
        subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        QMessageBox.critical(window, "Scrcpy Error", str(e))


def on_record_clicked():
    item = appList.currentItem()
    if not item:
        QMessageBox.information(
            window, "No Selection", "Please select an app from the list."
        )
        return

    package_name = item.text()
    file_name = datetime.now().strftime("%Y_%m_%d-%H_%M_%S")

    command = [
        tool_path("scrcpy.exe"),
        "--new-display",
        "--start-app",
        package_name,
        "--record",
        f"{file_name}.mp4",
    ]

    try:
        subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        QMessageBox.critical(window, "Scrcpy Error", str(e))


def check_adb_device():

    # open_auto_connect()

    try:
        output = subprocess.check_output(
            [tool_path("adb"), "devices"],
            text=True,
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        print(output)

    except Exception:
        status.setText("ADB not found")
        return False

    lines = output.strip().splitlines()[1:]  # skip header

    if not lines:
        status.setText("No device")
        return False

    for line in lines:
        serial, state = line.split("\t")

        device_name = subprocess.check_output(
            [tool_path("adb"), "-s", serial, "shell", "getprop", "ro.product.model"],
            text=True,
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        device.setText(f"Device: {device_name.strip()}")

        if state == "device":
            status.setText("Status: Connected🟢")

            fill_app_list()
            return True

        if state == "offline":
            status.setText("Status: Offline🔴")
            return False

        if state == "unauthorized":
            status.setText("Status: Unauthorized⚠️")
            return False

    return False


def get_packages():
    try:
        out = subprocess.check_output(
            [tool_path("adb"), "shell", "pm", "list", "packages", "-3"],
            text=True,
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return [line.replace("package:", "") for line in out.splitlines()]
    except Exception as e:
        QMessageBox.warning(window, "ADB Error", str(e))
        return []


def fill_app_list():
    global all_apps
    all_apps = sorted(get_packages())

    appList.clear()
    for pkg in all_apps:
        appList.addItem(pkg)


def on_search_changed(text):
    appList.clear()

    text = text.lower()

    for app in all_apps:
        if text in app.lower():
            appList.addItem(app)


def open_auto_connect():
    try:
        output = subprocess.check_output(
            ["netsh", "interface", "ip", "show", "config", "name=Wi-Fi"],
            encoding="utf-8",
            text=True,
            errors="ignore",
        )
    except Exception as e:
        QMessageBox.critical(window, "Network Error", str(e))
        return

    match = re.search(r"Default Gateway:\s+([\d.]+)", output)

    if not match:
        QMessageBox.warning(
            window, "Auto Connect Failed", "Could not detect Wi-Fi gateway IP."
        )
        return

    gateway_ip = match.group(1)

    subprocess.run(
        [tool_path("adb"), "tcpip", "5555"], creationflags=subprocess.CREATE_NO_WINDOW
    )

    result = subprocess.run(
        [tool_path("adb"), "connect", f"{gateway_ip}:5555"],
        capture_output=True,
        text=True,
    )

    print(result)
    fill_app_list()

    if "connected" in result.stdout.lower():
        QMessageBox.information(
            window, "Connected", f"Connected to device at {gateway_ip}:5555"
        )
    else:
        QMessageBox.warning(window, "Connection Failed", result.stdout or result.stderr)


def first_setup():
    QMessageBox.information(
        window,
        "First Time Setup",
        "Please ensure ADB is set up correctly and your device is connected via USB.",
    )

    command = [tool_path("adb"), "tcpip", "5555"]
    print(command)

    try:
        subprocess.run(command, capture_output=True, text=True)

        open_auto_connect()
    except Exception as e:
        QMessageBox.critical(window, "ADB Error", str(e))
        return


def open_manual_connect():
    file = QFile(resource_path("manual.ui"))
    file.open(QFile.ReadOnly)
    loader = QUiLoader()
    dialog = loader.load(file, window)
    file.close()

    ipInput = dialog.findChild(QLineEdit, "txtIp")
    portInput = dialog.findChild(QLineEdit, "txtPort")
    connectBtn = dialog.findChild(QPushButton, "connectBtn")
    cancelBtn = dialog.findChild(QPushButton, "cancelBtn")

    def adb_connect():
        ip = ipInput.text().strip()
        port = portInput.text().strip()

        if not ip:
            QMessageBox.information(
                dialog, "Input Error", "Please enter both IP address and port."
            )
            return
        if not port:
            port = "5555"

        command = [tool_path("adb"), "connect", f"{ip}:{port}"]

        try:
            output = subprocess.run(command, capture_output=True, text=True)
            QMessageBox.information(dialog, "ADB Connect", output.stdout.strip())

        except Exception as e:
            QMessageBox.critical(dialog, "ADB Error", str(e))
            return
        dialog.accept()

    cancelBtn.clicked.connect(dialog.close)
    connectBtn.clicked.connect(adb_connect)
    dialog.exec()


def open_help():
    file = QFile(resource_path("help.ui"))
    file.open(QFile.ReadOnly)

    loader = QUiLoader()
    dialog = loader.load(file, window)
    file.close()

    dialog.exec()


def open_about():
    file = QFile(resource_path("about.ui"))
    file.open(QFile.ReadOnly)

    loader = QUiLoader()
    dialog = loader.load(file, window)
    file.close()

    dialog.exec()


startBtn.clicked.connect(on_start_clicked)
recordBtn.clicked.connect(on_record_clicked)
searchInput.textChanged.connect(on_search_changed)
manualAction.triggered.connect(open_manual_connect)
autoAction.triggered.connect(open_auto_connect)
helpAction.triggered.connect(open_help)
aboutAction.triggered.connect(open_about)

# fill_app_list()
check_adb_device()

window.show()
sys.exit(app.exec())
