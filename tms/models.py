# tms/models.py → FINAL: WITH is_active FOR ADMINS

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from datetime import date
import uuid
import os

# NEW: For trigram (typo tolerance) and full-text search
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

# ======================= HELPER: SAFE FILENAME =======================
def safe_filename(filename):
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    return f"{slugify(name)[:50]}{ext}"

# ======================= UPLOAD PATHS =======================
def store_logo_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    return f"{instance.slug}/logos/logo{ext}"

def category_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.store.slug}/categories/{safe_name}"

def product_video_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.store.slug}/products/{instance.slug}/videos/{safe_name}"

def product_image_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.product.store.slug}/products/{instance.product.slug}/{safe_name}"

def banner_desktop_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.store.slug}/banners/desktop/{safe_name}"

def banner_tablet_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.store.slug}/banners/tablet/{safe_name}"

def banner_mobile_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    safe_name = safe_filename(filename)
    return f"{instance.store.slug}/banners/mobile/{safe_name}"


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

    def __str__(self):
        return self.name


class StoreAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_admins')
    is_active = models.BooleanField(default=True)  # ← NEW: For enable/disable

    def __str__(self):
        return f"{self.user.username} → {self.store.name} ({'Active' if self.is_active else 'Disabled'})"


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

    # NEW: For full-text search (optional future upgrade)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            # Trigram indexes for typo tolerance (soofa → sofa)
            GinIndex(name='name_trgm_idx', fields=['name'], opclasses=['gin_trgm_ops']),
            GinIndex(name='short_desc_trgm_idx', fields=['short_desc'], opclasses=['gin_trgm_ops']),
            # Full-text GIN index (when you enable search_vector)
            GinIndex(fields=['search_vector'], name='product_search_gin'),
            models.Index(fields=['store']),
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
            self.discount_percent = int(discount)
        else:
            self.discount_percent = None
        super().save(*args, **kwargs)

    def is_deal_active(self):
        return self.deal_end_date and self.deal_end_date >= date.today()

    def get_price_display(self):
        if self.offer_price:
            prefix = "Deal Price: " if self.is_deal_active() else ""
            return f"{prefix}₹{self.offer_price:,.0f}"
        return "Call for Best Price"

    def __str__(self):
        return f"{self.name} - {self.store.name}"


# Rest of models unchanged (ProductSpecification, ProductImage, etc.)
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
    class Meta:
        ordering = ['order', '-created_at']
    def __str__(self):
        return f"{self.store.name} - Banner"

class Lead(models.Model):
    STATUS_CHOICES = [('new','New Enquiry'),('contacted','Contacted'),('Converted','Converted'),('Just Enquiry','Just Enquiry')]
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
    def __str__(self):
        return f"{self.customer_name} → {self.store.name}"
    
    def get_status_display(self):
        for val, label in self.STATUS_CHOICES:
            if val == self.status:
                return label
        return self.status
    
    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['store']),
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
        return f"{self.get_platform_display()}"
    def get_icon_class(self):
        icons = {
            'facebook': 'fab fa-facebook-f', 'instagram': 'fab fa-instagram',
            'youtube': 'fab fa-youtube', 'twitter': 'fab fa-twitter',
            'whatsapp': 'fab fa-whatsapp', 'linkedin': 'fab fa-linkedin-in',
            'tiktok': 'fab fa-tiktok'
        }
        return icons.get(self.platform, 'fas fa-link')