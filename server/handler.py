"""HTTP request handler for browsing and viewing files."""

import html
import mimetypes
import os
import urllib.parse
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler

from config import FILE_AUTH_SESSION_DAYS, ROOT_FOLDER, SESSION_COOKIE_NAME
from server.auth import (
    clear_session_cookie,
    create_session,
    destroy_session,
    get_cookie,
    is_auth_configured,
    is_authenticated,
    set_session_cookie,
    verify_credentials,
)
from server.templates import render_template
from server.urls import build_path_url

HTML_CONTENT_TYPE = "text/html; charset=utf-8"


class SimpleHandler(BaseHTTPRequestHandler):
    """HTTP handler for the home page, file browser, and file viewing."""

    def _send_html(self, content, status=200, extra_headers=None):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", HTML_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))

        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)

        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)

        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)

        self.end_headers()

    def _login_url(self, next_path):
        return "/login?next=" + urllib.parse.quote(next_path, safe="")

    def _require_file_auth(self):
        """Return True when the client may access file routes."""
        if not is_auth_configured():
            self._send_html(render_template("auth_disabled.html"), status=503)
            return False

        if is_authenticated(self):
            return True

        next_path = self.path.split("?", 1)[0]
        self._redirect(self._login_url(next_path))
        return False

    def _parse_form_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        return urllib.parse.parse_qs(body)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])

        if path == "/login":
            self.show_login()
            return

        if path == "/logout":
            self.logout()
            return

        if path.startswith("/files"):
            self.show_files(path)
            return

        if path.startswith("/view"):
            self.view_file(path)
            return

        self._send_html(render_template("home.html"))

    def do_POST(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])

        if path == "/login":
            self.handle_login()
            return

        if path.startswith("/upload"):
            self.upload_file(path)
            return

        self.send_error(404)

    def show_login(self):
        if not is_auth_configured():
            self._send_html(render_template("auth_disabled.html"), status=503)
            return

        if is_authenticated(self):
            next_url = self._get_query_param("next", "/files")
            self._redirect(next_url)
            return

        next_url = html.escape(self._get_query_param("next", "/files"), quote=True)
        error = self._get_query_param("error", "")

        error_message = ""
        if error == "invalid":
            error_message = '<p class="error">Invalid username or password.</p>'

        page = render_template(
            "login.html",
            next_url=next_url,
            error_message=error_message,
            session_days=FILE_AUTH_SESSION_DAYS,
        )
        self._send_html(page)

    def handle_login(self):
        if not is_auth_configured():
            self._send_html(render_template("auth_disabled.html"), status=503)
            return

        form = self._parse_form_body()
        username = form.get("username", [""])[0]
        password = form.get("password", [""])[0]
        next_url = form.get("next", ["/files"])[0]

        if not next_url.startswith("/"):
            next_url = "/files"

        if verify_credentials(username, password):
            token = create_session()
            self.send_response(302)
            self.send_header("Location", next_url)
            set_session_cookie(self, token)
            self.end_headers()
            return

        login_url = (
            "/login?next="
            + urllib.parse.quote(next_url, safe="")
            + "&error=invalid"
        )
        self._redirect(login_url)

    def logout(self):
        token = get_cookie(self, SESSION_COOKIE_NAME)
        destroy_session(token)

        self.send_response(302)
        self.send_header("Location", "/login")
        clear_session_cookie(self)
        self.end_headers()

    def _get_query_param(self, name, default=""):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        values = params.get(name, [])
        return values[0] if values else default

    def show_files(self, url_path):
        if not self._require_file_auth():
            return

        relative_path = url_path.replace("/files", "").strip("/")
        folder_path = os.path.join(ROOT_FOLDER, relative_path)

        if not os.path.exists(folder_path):
            self.send_error(404, "Folder not found")
            return

        upload_path = html.escape("/upload/" + relative_path, quote=True)

        back_link = ""
        if relative_path:
            parent = os.path.dirname(relative_path).replace("\\", "/")
            back_link = (
                f'<a href="/files/{html.escape(parent)}" title="Go Back" style="display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; background-color: #edf2f7; color: #4a5568; text-decoration: none; border-radius: 6px; font-family: sans-serif; font-size: 16px; font-weight: bold; margin-bottom: 12px;">'
                "←</a>"
            )

        file_list = ""
        for item in sorted(os.listdir(folder_path)):
            item_path = os.path.join(folder_path, item)
            encoded_item = urllib.parse.quote(item, safe="")
            safe_name = html.escape(item)

            if os.path.isdir(item_path):
                href = html.escape(
                    build_path_url("/files", relative_path, encoded_item)
                )
                file_list += f'<div style="display: flex; align-items: center; gap: 8px; padding: 6px 0; font-family: sans-serif; font-size: 14px; border-bottom: 1px solid #f0f0f0;"><span style="font-size: 16px;">📁</span><a href="{href}" style="color: #2b6cb0; text-decoration: none; font-weight: 600;">{safe_name}</a></div>'
            else:
                href = html.escape(
                    build_path_url("/view", relative_path, encoded_item)
                )
                file_list += f'<div style="display: flex; align-items: center; gap: 8px; padding: 6px 0; font-family: sans-serif; font-size: 14px; border-bottom: 1px solid #f0f0f0;"><span style="font-size: 16px;">📄</span><a href="{href}" style="color: #0066cc; text-decoration: none; font-weight: 500;">{safe_name}</a></div>'

        page = render_template(
            "file_browser.html",
            upload_path=upload_path,
            back_link=back_link,
            file_list=file_list,
        )
        self._send_html(page)

    def upload_file(self, url_path):
        if not self._require_file_auth():
            return

        try:
            relative_path = url_path.replace("/upload", "").strip("/")
            folder_path = os.path.join(ROOT_FOLDER, relative_path)

            if not os.path.isdir(folder_path):
                page = render_template(
                    "error.html",
                    title="Folder not found",
                    message="The upload folder does not exist.",
                )
                self._send_html(page, status=404)
                return

            length = int(self.headers.get("Content-Length", 0))
            content_type = self.headers.get("Content-Type")

            if not content_type:
                page = render_template(
                    "error.html",
                    title="Missing content type",
                    message="The upload request did not include a content type.",
                )
                self._send_html(page, status=400)
                return

            body = self.rfile.read(length)

            message = BytesParser(policy=default).parsebytes(
                (
                    f"Content-Type: {content_type}\r\n"
                    "MIME-Version: 1.0\r\n\r\n"
                ).encode()
                + body
            )

            for part in message.iter_parts():
                filename = part.get_filename()

                if filename:
                    filename = os.path.basename(filename)
                    file_path = os.path.join(folder_path, filename)

                    with open(file_path, "wb") as file:
                        file.write(part.get_payload(decode=True))

                    self.send_response(303)
                    self.send_header("Location", f"/files/{relative_path}")
                    self.end_headers()
                    return

            page = render_template(
                "error.html",
                title="No file uploaded",
                message="Choose a file before uploading.",
            )
            self._send_html(page, status=400)

        except Exception as error:
            print(f"Upload failed: {repr(error)}")

            page = render_template(
                "upload_failed.html",
                error_detail=html.escape(repr(error)),
            )
            self._send_html(page, status=500)

    def view_file(self, url_path):
        if not self._require_file_auth():
            return

        relative_path = url_path.replace("/view/", "")

        file_path = os.path.join(
            ROOT_FOLDER,
            urllib.parse.unquote(relative_path),
        )

        if not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return

        content_type, _ = mimetypes.guess_type(file_path)

        if content_type is None:
            content_type = "application/octet-stream"

        with open(file_path, "rb") as file:
            data = file.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", "inline")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
