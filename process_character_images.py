#!/usr/bin/env python3
"""
Process character images to remove white backgrounds and crop to show only characters.
"""
from PIL import Image
import os
from pathlib import Path

def remove_white_background(img, threshold=230):
    """Remove white/light backgrounds and make them transparent."""
    img = img.convert("RGBA")
    data = img.getdata()
    
    new_data = []
    for item in data:
        r, g, b = item[0], item[1], item[2]
        # If pixel is white/light (above threshold), make it transparent
        # Also check for beige/cream colors (common background colors)
        if (r > threshold and g > threshold and b > threshold) or \
           (abs(r - g) < 20 and abs(g - b) < 20 and r > 200):  # Beige/cream colors
            new_data.append((255, 255, 255, 0))  # Transparent
        else:
            new_data.append(item)
    
    img.putdata(new_data)
    return img

def find_character_bounds(img):
    """Find the bounding box of the character (non-transparent area)."""
    # Get bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox is None:
        return None
    
    # Minimal padding - we want tight crop
    padding = 2
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - padding),
        max(0, y0 - padding),
        min(img.width, x1 + padding),
        min(img.height, y1 + padding)
    )

def process_image(input_path, output_path, crop_percentages=(0.15, 0.15, 0.35, 0.15)):
    """Process a single image: remove background and crop."""
    try:
        img = Image.open(input_path)
        
        # Step 1: Remove white/light background first
        img = remove_white_background(img, threshold=230)
        
        # Step 2: Aggressively crop to remove borders and text areas
        # crop_percentages: (top, right, bottom, left)
        # More aggressive cropping to remove text at top/bottom and borders on sides
        width, height = img.size
        left = int(width * crop_percentages[3])
        top = int(height * crop_percentages[0])  # Remove more from top (text area)
        right = width - int(width * crop_percentages[1])
        bottom = height - int(height * crop_percentages[2])  # Remove more from bottom (text area)
        
        img = img.crop((left, top, right, bottom))
        
        # Step 3: Remove any remaining white/light pixels that might be borders
        img = remove_white_background(img, threshold=235)
        
        # Step 4: Find actual character bounds (only non-transparent pixels) and crop tightly
        bbox = find_character_bounds(img)
        if bbox:
            img = img.crop(bbox)
        
        # Step 5: Final pass to remove any white pixels that might have been exposed
        img = remove_white_background(img, threshold=235)
        
        # Step 6: Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "PNG")
        print(f"Processed: {input_path.name} -> {output_path.name}")
        return True
    except Exception as e:
        print(f"Error processing {input_path.name}: {e}")
        return False

def main():
    # Paths
    script_dir = Path(__file__).parent
    input_dir = script_dir / "frontend" / "public" / "8bit-roleplaycards"
    output_dir = script_dir / "frontend" / "public" / "8bit-roleplaycards-processed"
    
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}")
        return
    
    # Process all PNG files
    image_files = list(input_dir.glob("*.png"))
    print(f"Found {len(image_files)} images to process...")
    
    processed = 0
    for img_path in sorted(image_files):
        output_path = output_dir / img_path.name
        if process_image(img_path, output_path):
            processed += 1
    
    print(f"\nProcessed {processed}/{len(image_files)} images successfully!")
    print(f"Output directory: {output_dir}")

if __name__ == "__main__":
    main()
