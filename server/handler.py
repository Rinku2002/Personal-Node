"""HTTP request handler for browsing, viewing, creating folders, and deleting files."""

import html
import mimetypes
import os
import shutil
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
    """HTTP handler for the home page, file browser, and file management."""

    # ----------------------------------------------------------------------
    # Helper Utilities
    # ----------------------------------------------------------------------

    def _is_safe_path(self, target_path):
        """Ensure target path resides inside ROOT_FOLDER to prevent path traversal."""
        abs_root = os.path.abspath(ROOT_FOLDER)
        abs_target = os.path.abspath(target_path)
        return os.path.commonpath([abs_root, abs_target]) == abs_root

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

    def _get_query_param(self, name, default=""):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        values = params.get(name, [])
        return values[0] if values else default

    # ----------------------------------------------------------------------
    # Request Dispatchers
    # ----------------------------------------------------------------------

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

        if path.startswith("/mkdir"):
            self.create_folder(path)
            return

        if path.startswith("/delete"):
            self.delete_item(path)
            return

        self.send_error(404)

    # ----------------------------------------------------------------------
    # Auth Views
    # ----------------------------------------------------------------------

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

    # ----------------------------------------------------------------------
    # File Operations Views
    # ----------------------------------------------------------------------

    def show_files(self, url_path):
        if not self._require_file_auth():
            return

        relative_path = url_path.replace("/files", "").strip("/")
        folder_path = os.path.join(ROOT_FOLDER, relative_path)

        if not self._is_safe_path(folder_path) or not os.path.exists(folder_path):
            self.send_error(404, "Folder not found")
            return

        upload_path = html.escape("/upload/" + relative_path, quote=True)
        mkdir_path = html.escape("/mkdir/" + relative_path, quote=True)

        display_path = "/" + urllib.parse.unquote(relative_path) if relative_path else "/"
        safe_display_path = html.escape(display_path)

        back_link_html = (
            '<div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px; max-width: 100%;">'
        )

        if relative_path:
            parent = os.path.dirname(relative_path).replace("\\", "/")
            back_link_html += (
                f'<a href="/files/{html.escape(parent)}" title="Go Back" style="display: inline-flex; flex-shrink: 0; align-items: center; justify-content: center; width: 32px; height: 32px; background-color: #f1f5f9; color: #475569; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: bold;">'
                "←</a>"
            )

        back_link_html += (
            f'<span style="font-size: 16px; font-weight: 600; color: #1e293b; '
            f'word-break: break-word; overflow-wrap: anywhere; line-height: 32px;">{safe_display_path}</span></div>'
        )

        file_list = ""
        for item in sorted(os.listdir(folder_path)):
            item_path = os.path.join(folder_path, item)
            encoded_item = urllib.parse.quote(item, safe="")
            safe_name = html.escape(item)

            item_rel_path = (relative_path + "/" + item).strip("/")
            delete_action_url = html.escape("/delete/" + item_rel_path)

            is_dir = os.path.isdir(item_path)
            
            # SVG File & Directory Icons
            if is_dir:
                icon_svg = '<svg style="width:20px;height:20px;stroke:#2563eb;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>'
                base_route = "/files"
                text_color = "#1d4ed8"
            else:
                icon_svg = '<svg style="width:20px;height:20px;stroke:#64748b;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>'
                base_route = "/view"
                text_color = "#334155"

            href = html.escape(build_path_url(base_route, relative_path, encoded_item))

            # Item row with SVG 3-dot menu and SVG trash icon
            file_list += f"""
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; font-size: 14px; border-bottom: 1px solid #f1f5f9;">
                <div style="display: flex; align-items: center; gap: 10px; overflow: hidden;">
                    <span style="flex-shrink: 0; display: flex; align-items: center;">{icon_svg}</span>
                    <a href="{href}" style="color: {text_color}; text-decoration: none; font-weight: 500; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">{safe_name}</a>
                </div>
                <details style="position: relative; cursor: pointer;">
                    <summary style="list-style: none; user-select: none; padding: 4px 8px; border-radius: 4px; display: flex; align-items: center;">
                        <svg style="width:18px;height:18px;stroke:#94a3b8;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;" viewBox="0 0 24 24"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>
                    </summary>
                    <div style="position: absolute; right: 0; top: 100%; margin-top: 4px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); z-index: 10; min-width: 130px; padding: 4px 0;">
                        <form action="{delete_action_url}" method="POST" onsubmit="return confirm('Delete {safe_name}?');" style="margin: 0;">
                            <button type="submit" style="width: 100%; text-align: left; background: none; border: none; padding: 8px 12px; font-size: 13px; color: #ef4444; cursor: pointer; font-weight: 500; display: flex; align-items: center; gap: 8px;">
                                <svg style="width:15px;height:15px;stroke:#ef4444;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                Delete
                            </button>
                        </form>
                    </div>
                </details>
            </div>
            """

        page = render_template(
            "file_browser.html",
            upload_path=upload_path,
            mkdir_path=mkdir_path,
            back_link=back_link_html,
            file_list=file_list,
        )
        self._send_html(page)

    def create_folder(self, url_path):
        """Handle directory creation."""
        if not self._require_file_auth():
            return

        relative_path = url_path.replace("/mkdir", "").strip("/")
        folder_path = os.path.join(ROOT_FOLDER, relative_path)

        if not self._is_safe_path(folder_path) or not os.path.isdir(folder_path):
            self.send_error(400, "Invalid base directory")
            return

        form = self._parse_form_body()
        new_folder_name = form.get("foldername", [""])[0].strip()

        if not new_folder_name or "/" in new_folder_name or "\\" in new_folder_name:
            page = render_template(
                "error.html",
                title="Invalid Name",
                message="Folder name cannot be empty or contain slashes.",
            )
            self._send_html(page, status=400)
            return

        target_dir = os.path.join(folder_path, new_folder_name)

        if not self._is_safe_path(target_dir):
            self.send_error(403, "Access denied")
            return

        try:
            os.makedirs(target_dir, exist_ok=False)
            self._redirect(f"/files/{relative_path}")
        except FileExistsError:
            page = render_template(
                "error.html",
                title="Folder Exists",
                message="A file or folder with that name already exists.",
            )
            self._send_html(page, status=400)
        except Exception as error:
            print(f"Mkdir failed: {repr(error)}")
            self.send_error(500, "Could not create folder")

    def delete_item(self, url_path):
        """Handle deletion of files or empty/non-empty directories."""
        if not self._require_file_auth():
            return

        relative_path = url_path.replace("/delete", "").strip("/")
        target_path = os.path.join(ROOT_FOLDER, relative_path)

        if not self._is_safe_path(target_path) or not os.path.exists(target_path):
            self.send_error(404, "Item not found")
            return

        parent_rel_path = os.path.dirname(relative_path).replace("\\", "/")

        try:
            if os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)

            self._redirect(f"/files/{parent_rel_path}")
        except Exception as error:
            print(f"Delete failed: {repr(error)}")
            page = render_template(
                "error.html",
                title="Delete Failed",
                message=f"Could not delete item: {html.escape(str(error))}",
            )
            self._send_html(page, status=500)

    def upload_file(self, url_path):
        if not self._require_file_auth():
            return

        try:
            relative_path = url_path.replace("/upload", "").strip("/")
            folder_path = os.path.join(ROOT_FOLDER, relative_path)

            if not self._is_safe_path(folder_path) or not os.path.isdir(folder_path):
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

                    if not self._is_safe_path(file_path):
                        self.send_error(403, "Access denied")
                        return

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

        if not self._is_safe_path(file_path) or not os.path.isfile(file_path):
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
