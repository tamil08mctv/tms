# tms/models.py → FINAL: HYBRID FAST WEBP CONVERSION (INSTANT UI + BACKGROUND OPTIMIZATION)

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from datetime import date
import uuid
import os
import threading
from PIL import Image as PILImage
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone as dj_timezone
from django.utils.timezone import localtime

# For search
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField


# ======================= SAFE FILENAME =======================
def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    return f"{slugify(name)[:50]}{ext.lower()}"


# ======================= UPLOAD PATHS (FORCE .WEBP) =======================
def store_logo_path(instance, filename):
    name = os.path.splitext(safe_filename(filename))[0]
    return f"{instance.slug}/logos/{name}.webp"

def category_image_path(instance, filename):
    name = os.path.splitext(safe_filename(filename))[0]
    return f"{instance.store.slug}/categories/{name}.webp"

def product_video_path(instance, filename):
    return f"{instance.store.slug}/products/{instance.slug}/videos/{safe_filename(filename)}"

def product_image_path(instance, filename):
    return f"{instance.product.store.slug}/products/{instance.product.slug}/{safe_filename(filename)}"


def banner_desktop_path(instance, filename):
    name = os.path.splitext(safe_filename(filename))[0]
    return f"{instance.store.slug}/banners/desktop/{name}.webp"

def banner_tablet_path(instance, filename):
    name = os.path.splitext(safe_filename(filename))[0]
    return f"{instance.store.slug}/banners/tablet/{name}.webp"

def banner_mobile_path(instance, filename):
    name = os.path.splitext(safe_filename(filename))[0]
    return f"{instance.store.slug}/banners/mobile/{name}.webp"


# ======================= WEBP CONVERSION =======================
def convert_to_webp_and_compress(image_field):
    if not image_field:
        return image_field
    
    if image_field.name.lower().endswith('.webp'):
        return image_field

    try:
        pil_image = PILImage.open(image_field)

        # Handle transparency
        if pil_image.mode in ('RGBA', 'LA', 'P'):
            background = PILImage.new('RGB', pil_image.size, (255, 255, 255))
            if pil_image.mode == 'P':
                pil_image = pil_image.convert('RGBA')
            background.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode == 'RGBA' else None)
            pil_image = background
        elif pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')

        buffer = BytesIO()
        pil_image.save(buffer, format='WEBP', quality=85, method=6)

        base_name = os.path.splitext(os.path.basename(image_field.name))[0]
        new_filename = f"{base_name}.webp"

        return ContentFile(buffer.getvalue(), name=new_filename)

    except Exception as e:
        print(f"WebP conversion failed: {e}")
        return image_field  # Fallback: keep original


# ======================= BACKGROUND CONVERSION (INSTANT UI) =======================
from django.db import transaction  # ← Add this import at the top if not already there

# ======================= BACKGROUND CONVERSION (PRODUCTION-SAFE) =======================
def async_webp_convert(instance, field_names):
    """Convert images in background thread — SAFE for production (Gunicorn/uWSGI)"""
    def _convert():
        try:
            updated_fields = []
            for field_name in field_names:
                image_field = getattr(instance, field_name)
                if image_field and image_field.name and not image_field.name.lower().endswith('.webp'):
                    new_image = convert_to_webp_and_compress(image_field)
                    if new_image and new_image != image_field:
                        # Delete old raw file safely
                        if image_field.storage.exists(image_field.name):
                            image_field.storage.delete(image_field.name)
                        setattr(instance, field_name, new_image)
                        updated_fields.append(field_name)
            if updated_fields:
                instance.save(update_fields=updated_fields)
        except Exception as e:
            print(f"Async WebP conversion failed: {e}")

    # Critical fix: Run only after DB transaction commits
    transaction.on_commit(lambda: threading.Thread(target=_convert, daemon=True).start())
    
# ======================= MODELS =======================
class Store(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to=store_logo_path, blank=True, null=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    whatsapp = models.CharField(max_length=15)
    email = models.EmailField()
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    map_link = models.URLField(blank=True, null=True)
    working_hours = models.CharField(max_length=100, default="10 AM - 9 PM")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_stores')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Store.objects.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug

        super().save(*args, **kwargs)

        if self.logo:
            async_webp_convert(self, ['logo'])

    def __str__(self):
        return self.name


class StoreAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_admins')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} → {self.store.name}"


class Category(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)
    image = models.ImageField(upload_to=category_image_path, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Category.objects.filter(slug=slug, store=self.store).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug

        super().save(*args, **kwargs)

        if self.image:
            async_webp_convert(self, ['image'])

    def __str__(self):
        return f"{self.store.name} - {self.name}"


class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, blank=True, unique=True)
    short_desc = models.TextField(max_length=500)
    description = models.TextField(blank=True)
    regular_price = models.DecimalField(max_digits=12, decimal_places=0)
    offer_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    deal_end_date = models.DateField(null=True, blank=True)
    video = models.FileField(upload_to=product_video_path, blank=True, null=True)
    in_stock = models.BooleanField(default=True)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_limited_deal = models.BooleanField(default=False)
    is_special_offer = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    call_for_price = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0)
    enquiry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    search_vector = SearchVectorField(null=True, blank=True)


    class Meta:
        ordering = ['name']  # ← Default alphabetical order A → Z
        
        indexes = [
            GinIndex(name='name_trgm_idx', fields=['name'], opclasses=['gin_trgm_ops']),
            GinIndex(name='short_desc_trgm_idx', fields=['short_desc'], opclasses=['gin_trgm_ops']),
            GinIndex(fields=['search_vector'], name='product_search_gin'),
            
            models.Index(fields=['store', 'is_featured', 'is_best_seller']),
            models.Index(fields=['store', 'deal_end_date']),
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['store', 'category']),
            models.Index(fields=['store', 'in_stock', 'is_featured']),
            models.Index(fields=['store', 'created_at', 'is_new_arrival']),
            
            models.Index(fields=['-created_at', '-id'], name='idx_created_at_desc_id_desc'),
            models.Index(fields=['created_at', 'id'], name='idx_created_at_asc_id_asc'),
            
            models.Index(fields=['-offer_price', '-id'], name='idx_offer_price_desc_id_desc', condition=models.Q(offer_price__isnull=False)),
            models.Index(fields=['offer_price', 'id'], name='idx_offer_price_asc_id_asc', condition=models.Q(offer_price__isnull=False)),
            models.Index(fields=['-regular_price', '-id'], name='idx_regular_price_desc_id_desc', condition=models.Q(offer_price__isnull=True)),
            models.Index(fields=['regular_price', 'id'], name='idx_regular_price_asc_id_asc', condition=models.Q(offer_price__isnull=True)),
            
            models.Index(fields=['store', 'offer_price', 'regular_price'], name='idx_store_effective_price'),
            models.Index(fields=['store', '-created_at', '-id'], name='idx_store_created_desc'),
            models.Index(fields=['store', '-created_at'], name='idx_store_created_search', condition=models.Q(is_active=True)),
            
            # CRITICAL FOR ALPHABETICAL SPEED
            models.Index(fields=['name'], name='idx_product_name'),
    ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug

        if self.regular_price and self.offer_price and self.offer_price < self.regular_price:
            discount = ((self.regular_price - self.offer_price) / self.regular_price) * 100
            self.discount_percent = max(0, int(discount))
        else:
            self.discount_percent = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.store.name}"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    name = models.CharField(max_length=200)
    value = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.name}: {self.value}"

    class Meta:
        ordering = ['id']


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=product_image_path)
    is_main = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.image:
            async_webp_convert(self, ['image'])

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"Image - {self.product.name}"


class StoreBanner(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='banners')
    image_desktop = models.ImageField(upload_to=banner_desktop_path)
    image_tablet = models.ImageField(upload_to=banner_tablet_path, blank=True, null=True)
    image_mobile = models.ImageField(upload_to=banner_mobile_path)
    link = models.URLField(max_length=500, blank=True, null=True)
    caption = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        fields_to_convert = []
        for field in ['image_desktop', 'image_tablet', 'image_mobile']:
            image = getattr(self, field)
            if image:
                fields_to_convert.append(field)

        if fields_to_convert:
            async_webp_convert(self, fields_to_convert)

    class Meta:
        ordering = ['order', '-created_at']
        indexes = [models.Index(fields=['store', 'is_active', 'order'])]

    def __str__(self):
        return f"{self.store.name} - Banner"


class Lead(models.Model):
    STATUS_CHOICES = [('new','New Enquiry'),('contacted','Contacted'),('converted','Converted'),('just enquiry','just enquiry')]
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='leads')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=20, default='form')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def created_at_ist(self):
        """Returns created_at in Indian Standard Time"""
        return localtime(self.created_at).strftime('%d %b %Y, %I:%M %p')

    created_at_ist.short_description = 'Enquiry Time (IST)'

    def __str__(self):
        return f"{self.customer_name} → {self.store.name} ({self.created_at_ist()})"

    def __str__(self):
        return f"{self.customer_name} → {self.store.name}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', 'store']),
        ]


class SiteSettings(models.Model):
    SOCIAL_CHOICES = [('facebook','Facebook'),('instagram','Instagram'),('youtube','YouTube'),('twitter','Twitter'),('whatsapp','WhatsApp'),('linkedin','LinkedIn'),('tiktok','TikTok')]
    site_name = models.CharField(max_length=100, default="TMS Furnitures")
    logo = models.ImageField(upload_to="site/logo/", blank=True, null=True)
    favicon = models.ImageField(upload_to="site/favicon/", blank=True, null=True)
    phone = models.CharField(max_length=15, default="+91 96298 28969")
    email = models.EmailField(default="info@tmsfurnitures.com")
    address = models.TextField(default="Tamil Nadu's Most Trusted and Premium Brand")
    copyright_text = models.CharField(max_length=200, default="TMS Furniture | All rights reserved")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        fields = []
        if self.logo: fields.append('logo')
        if self.favicon: fields.append('favicon')

        if fields:
            async_webp_convert(self, fields)

    def __str__(self):
        return "Site Settings"

    class Meta:
        verbose_name_plural = "Site Settings"


class SocialLink(models.Model):
    settings = models.ForeignKey(SiteSettings, on_delete=models.CASCADE, related_name='social_links')
    platform = models.CharField(max_length=20, choices=SiteSettings.SOCIAL_CHOICES)
    url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.get_platform_display()

    def get_icon_class(self):
        icons = {
            'facebook': 'fab fa-facebook-f', 'instagram': 'fab fa-instagram',
            'youtube': 'fab fa-youtube', 'twitter': 'fab fa-twitter',
            'whatsapp': 'fab fa-whatsapp', 'linkedin': 'fab fa-linkedin-in',
            'tiktok': 'fab fa-tiktok'
        }
        return icons.get(self.platform, 'fas fa-link')