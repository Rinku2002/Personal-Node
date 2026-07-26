"""HTTP request handler for browsing and viewing files."""

import html
import mimetypes
import os
import urllib.parse
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler

from config import ROOT_FOLDER
from server.templates import FILE_BROWSER_HTML
from server.urls import build_path_url

HTML_CONTENT_TYPE = "text/html; charset=utf-8"


class SimpleHandler(BaseHTTPRequestHandler):
    """HTTP handler for the home page, file browser, and file viewing."""

    def _send_html(self, content, status=200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", HTML_CONTENT_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.unquote(self.path)

        if path.startswith("/files"):
            self.show_files(path)
            return

        if path.startswith("/view"):
            self.view_file(path)
            return

        self._send_html(
            "<h1>Hello! This is Manideep's Personal Host.</h1>"
        )

    def do_POST(self):
        path = urllib.parse.unquote(self.path)

        if path.startswith("/upload"):
            self.upload_file(path)
            return

        self.send_error(404)

    def show_files(self, url_path):
        relative_path = url_path.replace("/files", "").strip("/")
        folder_path = os.path.join(ROOT_FOLDER, relative_path)

        if not os.path.exists(folder_path):
            self.send_error(404, "Folder not found")
            return

        page = FILE_BROWSER_HTML

        upload_path = "/upload/" + relative_path

        page += f"""
        <form action="{html.escape(upload_path)}"
              method="post"
              enctype="multipart/form-data">
            <input type="file" name="file" required>
            <button type="submit">Upload</button>
        </form>
        <br>
        """

        if relative_path:
            parent = os.path.dirname(relative_path).replace("\\", "/")
            page += (
                f'<a href="/files/{html.escape(parent)}">'
                "&lt; Back</a><br><br>"
            )

        for item in sorted(os.listdir(folder_path)):
            item_path = os.path.join(folder_path, item)

            encoded_item = urllib.parse.quote(item, safe="")
            safe_name = html.escape(item)

            if os.path.isdir(item_path):
                href = html.escape(
                    build_path_url(
                        "/files",
                        relative_path,
                        encoded_item
                    )
                )
                page += (
                    f'[Folder] <a href="{href}">'
                    f'{safe_name}</a><br>'
                )

            else:
                href = html.escape(
                    build_path_url(
                        "/view",
                        relative_path,
                        encoded_item
                    )
                )
                page += (
                    f'[File] <a href="{href}">'
                    f'{safe_name}</a><br>'
                )

        page += "</body></html>"

        self._send_html(page)

    def upload_file(self, url_path):
        try:
            relative_path = url_path.replace("/upload", "").strip("/")
            folder_path = os.path.join(ROOT_FOLDER, relative_path)

            if not os.path.isdir(folder_path):
                self._send_html(
                    "<h3>Error: Folder not found</h3>",
                    status=404
                )
                return

            length = int(
                self.headers.get("Content-Length", 0)
            )

            content_type = self.headers.get("Content-Type")

            if not content_type:
                self._send_html(
                    "<h3>Error: Missing content type</h3>",
                    status=400
                )
                return

            body = self.rfile.read(length)

            message = BytesParser(
                policy=default
            ).parsebytes(
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

                    file_path = os.path.join(
                        folder_path,
                        filename
                    )

                    with open(file_path, "wb") as file:
                        file.write(
                            part.get_payload(decode=True)
                        )

                    self.send_response(303)
                    self.send_header(
                        "Location",
                        f"/files/{relative_path}"
                    )
                    self.end_headers()
                    return

            self._send_html(
                "<h3>Error: No file uploaded</h3>",
                status=400
            )

        except Exception as error:
            print(f"Upload failed: {repr(error)}")

            self._send_html(
                f"""
                <h3>Upload failed</h3>
                <pre>{html.escape(repr(error))}</pre>
                """,
                status=500
            )

    def view_file(self, url_path):
        relative_path = url_path.replace("/view/", "")

        file_path = os.path.join(
            ROOT_FOLDER,
            urllib.parse.unquote(relative_path)
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
        self.send_header(
            "Content-Type",
            content_type
        )
        self.send_header(
            "Content-Disposition",
            "inline"
        )
        self.send_header(
            "Content-Length",
            str(len(data))
        )
        self.end_headers()

        self.wfile.write(data)
