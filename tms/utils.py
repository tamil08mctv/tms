from PIL import Image as PILImage
from io import BytesIO
from django.core.files.base import ContentFile
import os

def convert_to_webp_in_memory(image_field):
    if not image_field or image_field.name.lower().endswith('.webp'):
        return None
    
    try:
        image_field.seek(0)
        pil_image = PILImage.open(image_field)
        
        # Handle transparency
        if pil_image.mode in ('RGBA', 'LA', 'P'):
            background = PILImage.new('RGB', pil_image.size, (255, 255, 255))
            if pil_image.mode == 'P':
                pil_image = pil_image.convert('RGBA')
            background.paste(
                pil_image,
                mask=pil_image.split()[-1] if pil_image.mode in ('RGBA', 'LA') else None
            )
            pil_image = background
        elif pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        buffer = BytesIO()
        pil_image.save(buffer, format='WEBP', quality=85, method=6)
        
        # ?? PRESERVE FULL DIRECTORY PATH
        original_path = image_field.name  # e.g. "tms-furniture/categories/living-room.jpg"
        dir_name = os.path.dirname(original_path)  # "tms-furniture/categories"
        base_name = os.path.splitext(os.path.basename(original_path))[0]  # "living-room"
        new_path = f"{dir_name}/{base_name}.webp" if dir_name else f"{base_name}.webp"
        
        return ContentFile(buffer.getvalue(), name=new_path)
    
    except Exception as e:
        print(f"WebP conversion failed: {e}")
        return None