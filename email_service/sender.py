"""Send email notifications when the server goes live."""

import smtplib
from email.mime.text import MIMEText

from config import APP_PASSWORD, RECEIVER_EMAIL, SENDER_EMAIL


def send_live_link_email(public_url):
    """Email the public file browser link."""
    message = (
        "Your personal file server is live:\n\n"
        f"{public_url}/files"
    )

    msg = MIMEText(message)
    msg["Subject"] = "Personal Node Live Link"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

    print("Email sent with file access link!")
