"""Entry point: ngrok discovery, email notification, and HTTP server startup."""

import argparse
import os
import sys
import time

import requests
from http.server import HTTPServer

from config import SERVER_PORT, SERVER_PORT_TEST, PROD_LOG_DIR
from server.auth import is_auth_configured
from email_service import send_live_link_email
from server import SimpleHandler

NGROK_WAIT_TIMEOUT = 300  # 5 minutes
NGROK_POLL_INTERVAL = 5


class LoggerWriter:
    """Redirects stdout/stderr writes to python's standard logger."""
    def __init__(self, write_func):
        self.write_func = write_func

    def write(self, message):
        if message.strip():  # Avoid logging pure blank lines/newlines separately
            self.write_func(message.strip())

    def flush(self):
        pass


def setup_logging(is_prod):
    """Direct output to a file if in production mode, otherwise keep terminal output."""
    if not is_prod:
        return

    # Ensure log directory exists
    os.makedirs(PROD_LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(PROD_LOG_DIR, "server.log")

    import logging
    logging.basicConfig(
        filename=log_file_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Redirect print statements and std errors to the log file
    sys.stdout = LoggerWriter(logging.info)
    sys.stderr = LoggerWriter(logging.error)

    print(f"--- Production Logging Started: {log_file_path} ---")


def get_ngrok_url(*, quiet=False):
    """Return the public ngrok URL from the local ngrok API, or None if unavailable."""
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
        return response.json()["tunnels"][0]["public_url"]
    except Exception as error:
        if not quiet:
            print(f"Could not connect to ngrok: {error}")
        return None


def wait_for_ngrok_url(service_port):
    """Poll ngrok until a public URL is available or the wait timeout expires."""
    ngrok_url = get_ngrok_url()
    if ngrok_url:
        return ngrok_url

    print(f"Waiting for ngrok (up to {NGROK_WAIT_TIMEOUT // 60} minutes)...")
    print(f"Start ngrok in another terminal: ngrok http {service_port}")

    deadline = time.monotonic() + NGROK_WAIT_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(NGROK_POLL_INTERVAL)
        ngrok_url = get_ngrok_url(quiet=True)
        if ngrok_url:
            return ngrok_url

    print("Timed out waiting for ngrok.")
    return None


def main():
    """Start the server and notify by email when ngrok is running."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Run using production server port"
    )
    args = parser.parse_args()

    # Enable log redirection for production mode
    setup_logging(args.prod)

    service_port = SERVER_PORT if args.prod else SERVER_PORT_TEST

    print(
        f"Starting {'production' if args.prod else 'test'} server on port {service_port}"
    )

    if not is_auth_configured():
        print(
            "WARNING: FILE_AUTH_USERNAME and FILE_AUTH_PASSWORD are not set. "
            "File browsing, viewing, and uploads are disabled."
        )

    ngrok_url = wait_for_ngrok_url(service_port)

    if ngrok_url:
        print(f"Found ngrok URL: {ngrok_url}")
        send_live_link_email(ngrok_url)

    print(f"Server running on port {service_port}")
    httpd = HTTPServer(("0.0.0.0", service_port), SimpleHandler)
    httpd.serve_forever()


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print(f"Got some exception when running the server: {e}")
            time.sleep(1)
