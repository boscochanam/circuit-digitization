#!/usr/bin/env python3
"""Send Chris the image subset instructions + file list."""
import os, base64
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = Path.home() / ".hermes" / "google_token.json"

def send(to, subject, body, attachment_path=None):
    creds = Credentials.from_authorized_user_file(str(TOKEN), ['https://www.googleapis.com/auth/gmail.send'])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN, 'w') as f:
            f.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)

    msg = MIMEMultipart('mixed')
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if attachment_path:
        with open(attachment_path, 'rb') as f:
            att = MIMEBase('text', 'plain')
            att.set_payload(f.read())
            encoders.encode_base64(att)
            att.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
            msg.attach(att)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    res = service.users().messages().send(userId='me', body={'raw': raw}).execute()
    return res['id'], res['threadId']

body = """Hey Chris,

Can you download the HDC-Recognition dataset from Roboflow so the backend/UI images match what I'm working with here?

Link: https://universe.roboflow.com/line-k1z2h/hdc-recognition-66e7m

Export format: YOLO OBB (Oriented Bounding Boxes)

Instructions:
1. Download the full dataset from the link above (it has ~4833 images total)
2. The exported images have filenames like "C100_D1_P1_jpg.rf.XXXX.jpg" — the ".rf.XXXX" suffix is Roboflow augmentation naming
3. Keep only the 1680 images listed in the attached file (match by stripping the .rf.XXXX suffix, e.g. "C100_D1_P1_jpg.rf.9a388425f0a1c8ee8b5d48c661e490b9.jpg" → "C100_D1_P1_jpg.jpg")
4. Place them all in a single directory named "images" — no subdirectories, no augmentation variants

The backend loads them sorted alphabetically by filename, so the exact 1680 files, sorted A→Z, determine the image index used across the UI. If you have a different set/ordering, the indices won't match and you'll see different images than expected.

I've also attached a Python snippet you can run to filter the Roboflow export:

```
from pathlib import Path
import shutil

# Your Roboflow export with .rf.XXXX suffixes
src = Path("/path/to/roboflow_export")
# Destination for cleaned images
dst = Path("/path/to/images")
dst.mkdir(parents=True, exist_ok=True)

# Load the 1680 filenames
keep = {l.strip() for l in open("_image_list_1680.txt")}

for f in src.glob("*.jpg"):
    base = f.name.split(".rf.")[0] + ".jpg"
    if base in keep:
        shutil.copy2(f, dst / base)

print(f"Copied {len(list(dst.glob('*.jpg')))} images")
```

Let me know if you need anything else.

Cheers,
clawsco (Bosco's AI assistant)"""

msg_id, thread_id = send(
    to='chrisdcosta777@gmail.com',
    subject='Circuit Digitization — Image Dataset for Backend/UI',
    body=body,
    attachment_path='/home/claw/circuit-digitization/_image_list_1680.txt'
)
print(f"Sent: id={msg_id}, threadId={thread_id}")
# Clean up
for f in ['_image_list_1680.txt', '_list_imgs.py']:
    p = Path('/home/claw/circuit-digitization') / f
    if p.exists():
        p.unlink()
print("Cleaned up temp files")
