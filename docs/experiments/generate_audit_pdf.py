#!/usr/bin/env python3
"""Generate CGHD1152 quality audit PDF — high resolution images."""
import json, re, io, os
from PIL import Image
import zipfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ZIP_PATH = '/home/claw/Downloads/cghd1152.zip'
OUTPUT = '/home/claw/workspace/cghd_quality_audit.pdf'
RESULTS_PATH = '/home/claw/workspace/cghd_reclassified.json'

def load_json(path):
    with open(path) as f:
        text = f.read()
    text = re.sub(r',\s*\]', ']', text)
    return json.loads(text)

results = load_json(RESULTS_PATH)

drafters = {}
for r in results:
    drafters.setdefault(r['drafter'], []).append(r)

def drafter_sort_key(d):
    num_str = d.split('_')[1]
    return (0, int(num_str)) if num_str.lstrip('-').isdigit() and '-' not in num_str else (1, 0)

sorted_drafters = sorted(drafters.keys(), key=drafter_sort_key)

VERDICT_COLORS = {
    'GOOD': colors.HexColor('#22c55e'),
    'MARGINAL': colors.HexColor('#f59e0b'),
    'REJECT': colors.HexColor('#ef4444'),
    'NODATA': colors.HexColor('#6b7280'),
}

# Larger landscape page — A4 landscape (297×210 mm ≈ 11.7×8.3 in)
PAGE_W, PAGE_H = landscape(A4)

# Margins
ML, MR, MT, MB = 40, 20, 36, 20

# Grid: 5 columns x 2 rows, bigger cells
COLS, ROWS = 5, 2
CELL_W = (PAGE_W - ML - MR) / COLS
CELL_H = (PAGE_H - MT - MB) / ROWS

# Target thumbnail size at ~200 DPI equivalent
# Cell inner width ≈ CELL_W - padding, we want ~250 px wide thumbnails
THUMB_W = 280
THUMB_H = 280

# Per-drafter summary
from collections import Counter

def draw_thumbnail(c, img_path, x, y, w, h, filename, verdict, paper_type, reason):
    border_color = VERDICT_COLORS.get(verdict, colors.grey)
    
    # Background
    c.setFillColor(colors.white)
    c.setStrokeColor(border_color)
    c.setLineWidth(2)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
    
    # Color accent bar at top
    c.setFillColor(border_color)
    c.rect(x + 2, y + h - 5, w - 4, 5, fill=1, stroke=0)
    
    # Filename
    c.setFillColor(colors.HexColor('#1f2937'))
    c.setFont("Helvetica", 6)
    c.drawCentredString(x + w/2, y + h - 14, filename[:28])
    
    # Verdict badge
    c.setFillColor(border_color)
    c.setFont("Helvetica-Bold", 8)
    badge_w = c.stringWidth(verdict, "Helvetica-Bold", 8) + 12
    c.setFillColor(border_color)
    c.roundRect(x + w - badge_w - 4, y + 3, badge_w, 13, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.drawCentredString(x + w - badge_w/2 - 4, y + 5, verdict)
    
    # Image
    try:
        with zipfile.ZipFile(ZIP_PATH) as zf:
            if img_path in zf.namelist():
                img_data = zf.read(img_path)
                pil_img = Image.open(io.BytesIO(img_data))
                
                # Resize to high-res thumbnail (keeps aspect ratio)
                img_ar = pil_img.width / pil_img.height
                target_w = THUMB_W
                target_h = int(target_w / img_ar)
                if target_h > THUMB_H:
                    target_h = THUMB_H
                    target_w = int(target_h * img_ar)
                
                pil_resized = pil_img.resize((target_w, target_h), Image.LANCZOS)
                img_reader = ImageReader(pil_resized)
                
                # Image area within cell (leaving room for labels)
                img_area_w = w - 8
                img_area_h = h - 22 - 22  # top label + bottom label
                
                # Scale image to fit, maintaining aspect ratio
                scale = min(img_area_w / pil_resized.width, img_area_h / pil_resized.height)
                draw_w = pil_resized.width * scale
                draw_h = pil_resized.height * scale
                ix = x + (w - draw_w) / 2
                iy = y + 20 + (img_area_h - draw_h) / 2
                
                c.drawImage(img_reader, ix, iy, draw_w, draw_h)
    except Exception as e:
        c.setFillColor(colors.lightgrey)
        c.rect(x + 4, y + 20, w - 8, h - 44, fill=1, stroke=0)
        c.setFillColor(colors.grey)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + w/2, y + h/2, "No image")
    
    # Paper type label at bottom
    c.setFillColor(colors.HexColor('#374151'))
    c.setFont("Helvetica", 5.5)
    pt_label = paper_type[:22]
    c.drawCentredString(x + 4, y + 11, pt_label)
    # Grid score
    c.setFillColor(colors.HexColor('#9ca3af'))
    c.setFont("Helvetica", 5)
    c.drawRightString(x + w - 4, y + 11, f"GS:{reason[:16]}")

c = canvas.Canvas(OUTPUT, pagesize=(PAGE_W, PAGE_H))
c.setTitle("CGHD1152 Quality Audit — Paper-Type Classification")

for d in sorted_drafters:
    samples = drafters[d]
    verdict_order = {'GOOD': 0, 'MARGINAL': 1, 'REJECT': 2, 'NODATA': 3}
    samples.sort(key=lambda s: (verdict_order.get(s['verdict'], 9), s.get('grid_score', 99)))
    
    # Header
    c.setFillColor(colors.HexColor('#111827'))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(ML, PAGE_H - 18, f"Drafter: {d}")
    
    # Summary counts
    vc = Counter(s['verdict'] for s in samples)
    c.setFont("Helvetica", 9)
    x_off = ML + 110
    for vname, vcolor in [('GOOD', '#22c55e'), ('MARGINAL', '#f59e0b'), ('REJECT', '#ef4444'), ('NODATA', '#6b7280')]:
        cnt = vc.get(vname, 0)
        c.setFillColor(colors.HexColor(vcolor))
        c.drawString(x_off, PAGE_H - 18, f"{vname}:{cnt}")
        x_off += 60
    
    # Dominant paper types
    c.setFillColor(colors.HexColor('#6b7280'))
    c.setFont("Helvetica", 7)
    types = Counter(s['paper_type'] for s in samples)
    top_str = ', '.join(f'{t}({c})' for t, c in types.most_common(3))
    c.drawString(ML + 350, PAGE_H - 18, top_str[:90])
    
    # Separator line
    c.setStrokeColor(colors.HexColor('#e5e7eb'))
    c.setLineWidth(0.5)
    c.line(ML, PAGE_H - 26, PAGE_W - MR, PAGE_H - 26)
    
    # Thumbnails
    for i, s in enumerate(samples):
        col = i % COLS
        row = i // COLS
        x = ML + col * CELL_W + 3
        y = MB + (ROWS - 1 - row) * CELL_H + 3
        
        draw_thumbnail(c, s['path'], x, y, CELL_W - 6, CELL_H - 6,
                       s['filename'], s['verdict'], s['paper_type'], s.get('reason', ''))
    
    c.showPage()

c.save()
print(f"Saved: {OUTPUT}")
print(f"Pages: {len(sorted_drafters)}")
print(f"Size: {os.path.getsize(OUTPUT) / 1024:.0f} KB")
