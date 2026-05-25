#!/usr/bin/env python3
"""Send the CGHD quality audit PDF to Pranavesh."""
import os, base64
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = Path.home() / ".hermes" / "google_token.json"

def send(to, subject, body, attachments):
    creds = Credentials.from_authorized_user_file(str(TOKEN), ['https://www.googleapis.com/auth/gmail.send'])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN, 'w') as f: f.write(creds.to_json())
    service = build('gmail', 'v1', credentials=creds)
    msg = MIMEMultipart('mixed')
    msg['To'] = to
    msg['Subject'] = subject
    msg['From'] = '"clawsco" <clawscochanam@gmail.com>'
    msg.attach(MIMEText(body, 'plain'))
    for path in attachments:
        with open(path, 'rb') as f:
            att = MIMEBase('application', 'octet-stream')
            att.set_payload(f.read())
            encoders.encode_base64(att)
            att.add_header('Content-Disposition', 'attachment', filename=os.path.basename(path))
            msg.attach(att)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    res = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return res['id'], res['threadId']

msg_id, thread = send(
    to='pranavesh.talupuri@gmail.com',
    subject='CGHD Quality Audit — Full Dataset Analysis & Wire Detection Results',
    body="""Hi Pranavesh,

Bosco asked me to share the CGHD quality audit report with you.

This is a comprehensive VLM-based quality audit of the CGHD1152 dataset (1,152 circuit schematic images), covering image-level integrity issues, annotation quality, and class statistics.

Key findings in the report:
• 58 HDC component detection classes
• Quality scoring per image and per class
• Integrity issues identified across the dataset
• Visual summaries and class distribution charts

Dataset links mentioned in the repo:
• Source (CGHD1152): https://www.kaggle.com/datasets/johannesbayer/cghd1152
• HDC Recognition subset: https://app.roboflow.com/line-k1z2h/hdc-recognition-66e7m/models
• GitHub repo: https://github.com/boscochanam/circuit-digitization

The PDF is attached (compressed to ~5 MB for email delivery).

— clawsco (Bosco's AI assistant)""",
    attachments=['/home/claw/workspace/cghd_quality_audit_compressed.pdf']
)
print(f"Sent: {msg_id} thread={thread}")
