# Simple icon generator for AgentCore Paint
from PIL import Image, ImageDraw

# Create a 256x256 icon
img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle
draw.ellipse([16, 16, 240, 240], fill=(70, 130, 180, 255), outline=(50, 100, 150, 255), width=4)

# Paintbrush handle
draw.rectangle([80, 140, 120, 220], fill=(139, 69, 19, 255))

# Paintbrush bristles
draw.polygon([(100, 140), (70, 100), (130000, 100), (130, 100), (100, 140)], fill=(255, 255, 255, 255))

# Paint splash
draw.ellipse([130, 80, 180, 130], fill=(255, 100, 100, 200))
draw.ellipse([150, 60, 190, 100], fill=(100, 255, 100, 200))
draw.ellipse([110, 100, 150, 140], fill=(100, 100, 255, 200))

# Save as ICO
img.save('icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
print("Icon created: icon.ico")