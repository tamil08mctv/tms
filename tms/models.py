# tms/models.py — FINAL: FAST S3 UPLOAD + BACKGROUND WEBP CONVERSION WITH CELERY (FULLY FIXED)

import os
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.utils.timezone import localtime
from .tasks import convert_image_to_webp


def validate_video_size(value):
    limit_mb = 50
    limit_bytes = limit_mb * 1024 * 1024
    if value.size > limit_bytes:
        raise ValidationError(f"Video file too large. Maximum size is {limit_mb}MB. Your file is {value.size // (1024*1024)}MB.")


def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    return f"{slugify(name)[:50]}{ext.lower()}"


# Upload paths — keep original extension (no forced .webp)
def store_logo_path(instance, filename):
    return f"{instance.slug}/logos/{safe_filename(filename)}"


def category_image_path(instance, filename):
    return f"{instance.store.slug}/categories/{safe_filename(filename)}"


def product_video_path(instance, filename):
    return f"{instance.store.slug}/products/{instance.slug}/videos/{safe_filename(filename)}"


def product_image_path(instance, filename):
    return f"{instance.product.store.slug}/products/{instance.product.slug}/{safe_filename(filename)}"


def banner_desktop_path(instance, filename):
    return f"{instance.store.slug}/banners/desktop/{safe_filename(filename)}"


def banner_tablet_path(instance, filename):
    return f"{instance.store.slug}/banners/tablet/{safe_filename(filename)}"


def banner_mobile_path(instance, filename):
    return f"{instance.store.slug}/banners/mobile/{safe_filename(filename)}"


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
            convert_image_to_webp.delay('Store', self.id, 'logo')

    def __str__(self):
        return self.name


class StoreAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_admins')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ? {self.store.name}"


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
            convert_image_to_webp.delay('Category', self.id, 'image')

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
    video = models.FileField(
        upload_to=product_video_path,
        blank=True,
        null=True,
        validators=[validate_video_size],
        help_text="Max 30MB, MP4 recommended (30-60 seconds)"
    )
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
            convert_image_to_webp.delay('ProductImage', self.id, 'image')

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

        # Handle each image field safely
        if self.image_desktop and not str(self.image_desktop.name or '').lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_desktop != self.image_desktop:
                    convert_image_to_webp.delay('StoreBanner', self.id, 'image_desktop')
            else:
                convert_image_to_webp.delay('StoreBanner', self.id, 'image_desktop')

        if self.image_tablet and not str(self.image_tablet.name or '').lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_tablet != self.image_tablet:
                    convert_image_to_webp.delay('StoreBanner', self.id, 'image_tablet')
            else:
                convert_image_to_webp.delay('StoreBanner', self.id, 'image_tablet')

        if self.image_mobile and not str(self.image_mobile.name or '').lower().endswith('.webp'):
            if self.pk:
                old = StoreBanner.objects.get(pk=self.pk)
                if old.image_mobile != self.image_mobile:
                    convert_image_to_webp.delay('StoreBanner', self.id, 'image_mobile')
            else:
                convert_image_to_webp.delay('StoreBanner', self.id, 'image_mobile')

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
        return localtime(self.created_at).strftime('%d %b %Y, %I:%M %p')
    created_at_ist.short_description = 'Enquiry Time (IST)'

    def __str__(self):
        return f"{self.customer_name} ? {self.store.name} ({self.created_at_ist()})"

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

        if self.logo and not str(self.logo.name or '').lower().endswith('.webp'):
            if self.pk:
                old = SiteSettings.objects.get(pk=self.pk)
                if old.logo != self.logo:
                    convert_image_to_webp.delay('SiteSettings', self.id, 'logo')
            else:
                convert_image_to_webp.delay('SiteSettings', self.id, 'logo')

        if self.favicon and not str(self.favicon.name or '').lower().endswith('.webp'):
            if self.pk:
                old = SiteSettings.objects.get(pk=self.pk)
                if old.favicon != self.favicon:
                    convert_image_to_webp.delay('SiteSettings', self.id, 'favicon')
            else:
                convert_image_to_webp.delay('SiteSettings', self.id, 'favicon')

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