"""Generates assets/icon.ico — flat TF2-orange tile with a white wrench.
    python assets/make_icon.py
"""

import os

from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

d.rounded_rectangle([6, 6, S - 6, S - 6], radius=54,
                    fill=(197, 107, 44, 255), outline=(118, 60, 22, 255),
                    width=8)

# vertical wrench: round head with an open-end notch + handle
white = (246, 241, 231, 255)
orange = (197, 107, 44, 255)
d.ellipse([88, 30, 168, 110], fill=white)                    # head
d.rounded_rectangle([113, 84, 143, 196], radius=14, fill=white)  # handle
d.rectangle([116, 18, 140, 72], fill=orange)                 # open-end notch
d.ellipse([120, 58, 136, 74], fill=orange)                   # notch rounding

try:
    font = ImageFont.truetype("arialbd.ttf", 44)
except OSError:
    font = ImageFont.load_default()
d.text((S // 2, 218), "TF2", font=font, fill=white, anchor="mm")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])
print(f"yazildi: {out}")
