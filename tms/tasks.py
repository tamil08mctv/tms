from celery import shared_task
from django.apps import apps
from .utils import convert_to_webp_in_memory

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def convert_image_to_webp(self, model_name, object_id, field_name):
    try:
        Model = apps.get_model('tms', model_name)
        obj = Model.objects.get(id=object_id)
        image_field = getattr(obj, field_name)
        
        if not image_field or image_field.name.lower().endswith('.webp'):
            return
        
        old_path = image_field.name
        storage = image_field.storage
        
        converted = convert_to_webp_in_memory(image_field)
        if not converted:
            return
        
        # Save new WebP first
        image_field.save(converted.name, converted, save=False)
        obj.save(update_fields=[field_name])
        
        # Delete old only if different and exists
        if old_path != image_field.name and storage.exists(old_path):
            storage.delete(old_path)
            
    except Model.DoesNotExist:
        print(f"Object {model_name} id {object_id} not found")
    except Exception as exc:
        raise self.retry(exc=exc)