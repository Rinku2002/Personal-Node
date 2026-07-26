"""Personal Node CLI Manager"""

import argparse
import os
import subprocess
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(PROJECT_DIR, "bin")
LOG_FILE = os.path.join(PROJECT_DIR, "logs", "server.log")
VBS_FILE = os.path.join(BIN_DIR, "start-personal-node.vbs")


def kill_tasks(task_name):
    try:
        subprocess.run(
            ["cmd", "/c", "taskkill", "/f", "/im", task_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )

    except subprocess.CalledProcessError:
        print(f"{task_name} not found")

    print(f"{task_name} check completed")


def kill_python_tasks():
    """Kill only Personal Node server process."""

    subprocess.run(
        [
            "powershell",
            "-Command",
            "Get-CimInstance Win32_Process | "
            "Where-Object {$_.CommandLine -like '*main.py*'} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        ],
        capture_output=True,
        text=True
    )

    print("Personal Node server stopped.")


def stop_services():
    print("Stopping running services...")

    kill_tasks("ngrok.exe")
    kill_python_tasks()

    print("All services stopped.")


def start_prod():
    """Start production mode using start-personal-node.vbs."""

    stop_services()

    print("Starting production service in background...")

    subprocess.run(
        ["wscript", VBS_FILE],
        cwd=PROJECT_DIR
    )

    print("Production service started.")


def start_test():
    """Start test mode with visible terminals."""

    stop_services()

    print("Starting test service in terminal...")

    subprocess.Popen(
        ["start", "cmd", "/k", "ngrok http 8000"],
        shell=True,
        cwd=PROJECT_DIR
    )

    subprocess.run(
        [sys.executable, "main.py"],
        cwd=PROJECT_DIR
    )


def restart_services():
    """Restart production service."""

    print("Restarting service...")
    start_prod()


def check_status():
    """Show active ngrok and Python processes."""

    print("--- Running Processes ---")

    subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq ngrok.exe"]
    )

    print()

    subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq python.exe"]
    )


def stream_logs():
    """Stream live server logs."""

    if not os.path.exists(LOG_FILE):
        print(f"Log file not found: {LOG_FILE}")
        return

    print(f"Streaming logs from: {LOG_FILE}")
    print("-" * 60)

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            f.seek(0, os.SEEK_END)

            while True:
                line = f.readline()

                if line:
                    print(line, end="")
                else:
                    time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nStopped streaming logs.")


def main():
    parser = argparse.ArgumentParser(
        description="Personal Node CLI Manager"
    )

    parser.add_argument(
        "command",
        choices=[
            "prod",
            "test",
            "stop",
            "restart",
            "status",
            "logs",
        ],
        help="Command to execute"
    )

    args = parser.parse_args()

    commands = {
        "prod": start_prod,
        "test": start_test,
        "stop": stop_services,
        "restart": restart_services,
        "status": check_status,
        "logs": stream_logs,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
