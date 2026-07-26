"""Personal Node Setup Script"""

import os
import shutil
import winreg
import ctypes


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.basename(CURRENT_DIR).lower() == "bin":
    PROJECT_DIR = os.path.dirname(CURRENT_DIR)
else:
    PROJECT_DIR = CURRENT_DIR


BIN_DIR = os.path.join(PROJECT_DIR, "bin")
VBS_FILE = os.path.join(BIN_DIR, "start-personal-node.vbs")
CMD_FILE = os.path.join(BIN_DIR, "handle-personal-node.cmd")


def load_env():
    env_file = os.path.join(PROJECT_DIR, ".env")

    if not os.path.exists(env_file):
        return {}

    env = {}

    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()

    return env


ENV = load_env()
NGROK_DOMAIN = ENV.get("NGROK_DOMAIN")


def create_start_vbs():
    print("[1/4] Creating start-personal-node.vbs...")

    if NGROK_DOMAIN:
        ngrok_command = (
            f'ngrok http --domain={NGROK_DOMAIN} 8000'
        )
    else:
        ngrok_command = "ngrok http 8000"

    vbs_content = f"""Set WshShell = CreateObject("WScript.Shell")

WshShell.Run "cmd /c taskkill /f /im ngrok.exe", 0, True

WshShell.CurrentDirectory = "{PROJECT_DIR}"

WshShell.Run "{ngrok_command}", 0, False
WshShell.Run "python main.py --prod", 0, False
"""

    with open(VBS_FILE, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    print("Created:", VBS_FILE)

    if NGROK_DOMAIN:
        print("Using ngrok domain:", NGROK_DOMAIN)
    else:
        print("No NGROK_DOMAIN found. Using random ngrok URL.")


def add_vbs_to_startup():
    print("[2/4] Adding start-personal-node.vbs to Windows Startup...")

    startup_dir = os.path.join(
        os.environ["APPDATA"],
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )

    startup_file = os.path.join(startup_dir, "start-personal-node.vbs")

    shutil.copy2(VBS_FILE, startup_file)

    print("Created:", startup_file)


def create_command():
    print("[3/4] Creating handle-personal-node command...")

    os.makedirs(BIN_DIR, exist_ok=True)

    print("PROJECT_DIR :", PROJECT_DIR)
    print("BIN_DIR     :", BIN_DIR)
    print("CMD_FILE    :", CMD_FILE)
    print("CMD exists before:", os.path.exists(CMD_FILE))

    cmd_content = f"""@echo off
python "{os.path.join(BIN_DIR, 'handle-personal-node.py')}" %*
"""

    try:
        with open(CMD_FILE, "w", encoding="utf-8") as f:
            f.write(cmd_content)

        print("CMD written successfully.")
        print("CMD exists after :", os.path.exists(CMD_FILE))

    except Exception as e:
        print("ERROR creating CMD:", e)
        raise


def add_bin_to_path():
    print("[4/4] Updating PATH...")

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_ALL_ACCESS
    )

    try:
        current_path, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current_path = ""

    paths = [p.strip() for p in current_path.split(";") if p.strip()]

    if BIN_DIR not in paths:
        paths.append(BIN_DIR)

    winreg.SetValueEx(
        key,
        "Path",
        0,
        winreg.REG_EXPAND_SZ,
        ";".join(paths)
    )

    winreg.CloseKey(key)

    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF,
        0x001A,
        0,
        "Environment",
        0,
        1000,
        None
    )

    print("Added PATH:", BIN_DIR)


def main():
    print("=" * 60)
    print(" Personal Node Setup")
    print("=" * 60)

    create_start_vbs()
    add_vbs_to_startup()
    create_command()
    add_bin_to_path()

    print("=" * 60)
    print("Setup completed successfully")
    print("=" * 60)


if __name__ == "__main__":
    main()
