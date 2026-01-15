import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.utils.timezone import localtime
from django.conf import settings


try:
    from .tasks import convert_image_to_webp
except ImportError:
    convert_image_to_webp = None

def validate_video_size(value):
    limit_mb = 50
    limit_bytes = limit_mb * 1024 * 1024
    if value.size > limit_bytes:
        raise ValidationError(f"Video file too large. Maximum size is {limit_mb}MB.")

def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    return f"{slugify(name)[:50]}{ext.lower()}"

# Upload paths
def store_logo_path(instance, filename):
    return f"{instance.slug}/logos/{safe_filename(filename)}"

def category_image_path(instance, filename):
    return f"{instance.store.slug}/categories/{safe_filename(filename)}"

def product_video_path(instance, filename):
    return f"{instance.store.slug}/products/{instance.slug}/videos/{safe_filename(filename)}"

from django.utils.text import slugify
import os

def product_image_path(instance, filename):
    """
    Smart upload path:
    - For main product images: store/products/product-slug/filename
    - For variant images: store/products/product-slug/productname-variant_title/filename
    """
    # Get product safely
    if hasattr(instance, 'product'):
        product = instance.product
    elif hasattr(instance, 'variant') and hasattr(instance.variant, 'product'):
        product = instance.variant.product
    else:
        # Fallback
        safe_name = slugify(os.path.splitext(filename)[0])[:50]
        ext = os.path.splitext(filename)[1]
        return f"fallback/products/{safe_name}{ext}"

    if not product or not product.store or not product.slug:
        safe_name = slugify(os.path.splitext(filename)[0])[:50]
        ext = os.path.splitext(filename)[1]
        return f"fallback/products/{safe_name}{ext}"

    store_slug = slugify(product.store.name)[:50]
    product_slug = product.slug[:100]

    # Variant part: productname - variant_title (clean & readable)
    variant_part = ""
    if hasattr(instance, 'variant'):
        variant_title = instance.variant.get_display_title()
        if variant_title and variant_title != "Standard Variant":
            # Clean: slugify variant title, replace spaces with -, remove special chars
            clean_title = slugify(variant_title)[:80]
            variant_part = f"{product_slug}-{clean_title}/"
        else:
            variant_part = f"{product_slug}/"
    else:
        variant_part = f"{product_slug}/"

    # Safe filename
    name_part, ext = os.path.splitext(filename)
    safe_filename = slugify(name_part)[:100] + ext.lower()

    return f"{store_slug}/products/{variant_part}{safe_filename}"


def banner_desktop_path(instance, filename):
    return f"{instance.store.slug}/banners/desktop/{safe_filename(filename)}"

def banner_tablet_path(instance, filename):
    return f"{instance.store.slug}/banners/tablet/{safe_filename(filename)}"

def banner_mobile_path(instance, filename):
    return f"{instance.store.slug}/banners/mobile/{safe_filename(filename)}"

# ======================= SAFE WEBP CONVERSION HELPER =======================
def trigger_webp_conversion(model_name, instance_id, field_name):
    """
    Safely trigger WebP conversion only when Redis/Celery is enabled and available.
    In local development (USE_REDIS=False), it just logs and skips.
    """
    if not convert_image_to_webp:
        print(f"[DEV MODE] WebP task not available - skipping {model_name} #{instance_id} {field_name}")
        return

    if getattr(settings, 'USE_REDIS', False):
        try:
            convert_image_to_webp.delay(model_name, instance_id, field_name)
            print(f"[PRODUCTION] Queued WebP conversion: {model_name} #{instance_id} {field_name}")
        except Exception as e:
            print(f"[PRODUCTION] Celery failed (Redis down?): {e}")
    else:
        print(f"[DEV MODE] Skipped WebP conversion: {model_name} #{instance_id} {field_name}")

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

        trigger_conversion = False
        if self.pk:
            old = Store.objects.get(pk=self.pk)
            if old.logo != self.logo and self.logo and not str(self.logo.name or '').lower().endswith('.webp'):
                trigger_conversion = True
        else:
            if self.logo and not str(self.logo.name or '').lower().endswith('.webp'):
                trigger_conversion = True

        super().save(*args, **kwargs)

        if trigger_conversion:
            trigger_webp_conversion('Store', self.id, 'logo')

    def delete(self, *args, **kwargs):
        if self.logo:
            storage = self.logo.storage
            path = self.logo.name
            super().delete(*args, **kwargs)
            try:
                if storage.exists(path):
                    storage.delete(path)
            except Exception:
                pass
        else:
            super().delete(*args, **kwargs)

    def __str__(self):
        return self.name

class StoreAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_admins')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.store.name}"

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

        trigger_conversion = False
        if self.pk:
            old = Category.objects.get(pk=self.pk)
            if old.image != self.image and self.image and not str(self.image.name or '').lower().endswith('.webp'):
                trigger_conversion = True
        else:
            if self.image and not str(self.image.name or '').lower().endswith('.webp'):
                trigger_conversion = True

        super().save(*args, **kwargs)

        if trigger_conversion:
            trigger_webp_conversion('Category', self.id, 'image')

    def delete(self, *args, **kwargs):
        if self.image:
            storage = self.image.storage
            path = self.image.name
            super().delete(*args, **kwargs)
            try:
                if storage.exists(path):
                    storage.delete(path)
            except Exception:
                pass
        else:
            super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.store.name} - {self.name}"

class Product(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, blank=True, unique=True)
    short_desc = models.TextField(max_length=500)
    description = models.TextField(blank=True)
    regular_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    offer_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    deal_end_date = models.DateField(null=True, blank=True)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    video = models.FileField(upload_to=product_video_path, blank=True, null=True, validators=[validate_video_size])
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
        ordering = ['name']
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

    def delete(self, *args, **kwargs):
        if self.video:
            storage = self.video.storage
            path = self.video.name
            try:
                if storage.exists(path):
                    storage.delete(path)
            except Exception:
                pass
        self.images.all().delete()
        super().delete(*args, **kwargs)

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
        trigger_conversion = False
        if self.pk:
            old = ProductImage.objects.get(pk=self.pk)
            if old.image != self.image and self.image and not str(self.image.name or '').lower().endswith('.webp'):
                trigger_conversion = True
        else:
            if self.image and not str(self.image.name or '').lower().endswith('.webp'):
                trigger_conversion = True

        super().save(*args, **kwargs)

        if trigger_conversion:
            trigger_webp_conversion('ProductImage', self.id, 'image')

    def delete(self, *args, **kwargs):
        if self.image:
            storage = self.image.storage
            path = self.image.name
            super().delete(*args, **kwargs)
            try:
                if storage.exists(path):
                    storage.delete(path)
            except Exception:
                pass
        else:
            super().delete(*args, **kwargs)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"Image - {self.product.name}"
    


# ======================= PRODUCT VARIANTS =======================
class VariantAttribute(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variant_attributes')
    name = models.CharField(max_length=100, help_text="e.g., Color, Size, Material, Finish")

    class Meta:
        unique_together = ('product', 'name')
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} - {self.name}"

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    
    regular_price = models.DecimalField(max_digits=12, decimal_places=0)
    offer_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    
    in_stock = models.BooleanField(default=True)
    
    image = models.ImageField(upload_to=product_image_path, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.regular_price and self.offer_price and self.offer_price < self.regular_price:
            discount = ((self.regular_price - self.offer_price) / self.regular_price) * 100
            self.discount_percent = max(0, int(discount))
        else:
            self.discount_percent = None
        super().save(*args, **kwargs)

    def get_display_title(self):
        values = self.values.all().order_by('attribute__name')
        return " - ".join([v.value for v in values]) or "Standard Variant"

    def __str__(self):
        return f"{self.product.name} - {self.get_display_title()}"

class VariantValue(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='values')
    attribute = models.ForeignKey(VariantAttribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=200)

    class Meta:
        unique_together = ('variant', 'attribute')
        ordering = ['attribute__name']

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"
    
class ProductVariantImage(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=product_image_path)
    is_main = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"Image for {self.variant.get_display_title()}"

class VariantSpecification(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='specifications')
    name = models.CharField(max_length=200)
    value = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.name}: {self.value}"

    class Meta:
        ordering = ['id']


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
        # If updating (has pk), check for changed images and delete old ones
        if self.pk:
            old = StoreBanner.objects.get(pk=self.pk)

            # Desktop image changed
            if old.image_desktop != self.image_desktop and old.image_desktop:
                try:
                    old.image_desktop.storage.delete(old.image_desktop.name)
                except Exception:
                    pass

            # Tablet image changed
            if old.image_tablet != self.image_tablet and old.image_tablet:
                try:
                    old.image_tablet.storage.delete(old.image_tablet.name)
                except Exception:
                    pass

            # Mobile image changed
            if old.image_mobile != self.image_mobile and old.image_mobile:
                try:
                    old.image_mobile.storage.delete(old.image_mobile.name)
                except Exception:
                    pass

        super().save(*args, **kwargs)

        # Trigger WebP conversion (your existing logic)
        if self.image_desktop and not str(self.image_desktop.name or '').lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_desktop != self.image_desktop:
                    trigger_webp_conversion('StoreBanner', self.id, 'image_desktop')
            else:
                trigger_webp_conversion('StoreBanner', self.id, 'image_desktop')

        if self.image_tablet and self.image_tablet.name and not str(self.image_tablet.name).lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_tablet != self.image_tablet:
                    trigger_webp_conversion('StoreBanner', self.id, 'image_tablet')
            else:
                trigger_webp_conversion('StoreBanner', self.id, 'image_tablet')

        if self.image_mobile and not str(self.image_mobile.name or '').lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_mobile != self.image_mobile:
                    trigger_webp_conversion('StoreBanner', self.id, 'image_mobile')
            else:
                trigger_webp_conversion('StoreBanner', self.id, 'image_mobile')

    def delete(self, *args, **kwargs):
        # Delete all images on object delete
        storage = self.image_desktop.storage
        paths = [
            self.image_desktop.name if self.image_desktop else None,
            self.image_tablet.name if self.image_tablet else None,
            self.image_mobile.name if self.image_mobile else None,
        ]
        super().delete(*args, **kwargs)
        for path in paths:
            if path:
                try:
                    if storage.exists(path):
                        storage.delete(path)
                except Exception:
                    pass

    class Meta:
        ordering = ['order', '-created_at']
        indexes = [models.Index(fields=['store', 'is_active', 'order'])]

    def __str__(self):
        return f"{self.store.name} - Banner"

class Lead(models.Model):
    STATUS_CHOICES = [
        ('new', 'New Enquiry'),
        ('contacted', 'Contacted'),
        ('converted', 'Converted'),
        ('just enquiry', 'Just Enquiry'),
    ]

    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    store = models.ForeignKey(
        'Store',
        on_delete=models.CASCADE,
        related_name='leads'
    )
    product = models.ForeignKey(
        'Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )

    product_display_name = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Combined product name + selected variant (if any)"
    )

    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )
    
    source = models.CharField(max_length=20, default='form')
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def created_at_ist(self):
        return localtime(self.created_at).strftime('%d %b %Y, %I:%M %p')
    created_at_ist.short_description = 'Enquiry Time (IST)'

    def get_product_display(self):
        if self.product_display_name:
            return self.product_display_name.strip()
        if self.product and self.product.name:
            return self.product.name.strip()
        return "General Enquiry"

    def __str__(self):
        product_part = self.get_product_display()
        return f"{self.customer_name} - {product_part} ({self.store.name})"
    
    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', 'store']),
            models.Index(fields=['product']),
            models.Index(fields=['phone']),           # useful for duplicate checks
            models.Index(fields=['created_at', 'store']),
        ]
        ordering = ['-created_at']
        verbose_name = 'Lead / Enquiry'
        verbose_name_plural = 'Leads / Enquiries'


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

        if self.logo and not str(self.logo.name or '').lower().endswith('.webp'):
            if self.pk:
                old = SiteSettings.objects.get(pk=self.pk)
                if old.logo != self.logo:
                    trigger_webp_conversion('SiteSettings', self.id, 'logo')
            else:
                trigger_webp_conversion('SiteSettings', self.id, 'logo')

        if self.favicon and not str(self.favicon.name or '').lower().endswith('.webp'):
            if self.pk:
                old = SiteSettings.objects.get(pk=self.pk)
                if old.favicon != self.favicon:
                    trigger_webp_conversion('SiteSettings', self.id, 'favicon')
            else:
                trigger_webp_conversion('SiteSettings', self.id, 'favicon')

    def delete(self, *args, **kwargs):
        paths = [
            self.logo.name if self.logo else None,
            self.favicon.name if self.favicon else None,
        ]
        storage = self.logo.storage if self.logo else (self.favicon.storage if self.favicon else None)
        super().delete(*args, **kwargs)
        if storage:
            for path in paths:
                if path:
                    try:
                        if storage.exists(path):
                            storage.delete(path)
                    except Exception:
                        pass

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
            'facebook': 'fab fa-facebook-f',
            'instagram': 'fab fa-instagram',
            'youtube': 'fab fa-youtube',
            'twitter': 'fab fa-twitter',
            'whatsapp': 'fab fa-whatsapp',
            'linkedin': 'fab fa-linkedin-in',
            'tiktok': 'fab fa-tiktok'
        }
        return icons.get(self.platform, 'fas fa-link')
