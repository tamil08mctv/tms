# tms/models.py → FINAL CLEAN VERSION (NO ProductImage MODEL!)
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid

class Store(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to='stores/logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='stores/banners/', blank=True, null=True)
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
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class StoreAdmin(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='store_admins')
    def __str__(self):
        return f"{self.user.username} → {self.store.name}"


class Category(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.store.name} - {self.name}"


class Product(models.Model):
    PRICE_CHOICES = [
        ('fixed', 'Fixed Price'), ('starting', 'Starting From'),
        ('call', 'Call for Price'), ('request', 'Price on Request'), ('offer', 'Special Offer')
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, blank=True, unique=True)
    short_desc = models.TextField()
    description = models.TextField(blank=True)
    specs = models.TextField(default=dict, blank=True)

    price_style = models.CharField(max_length=20, choices=PRICE_CHOICES, default='call')
    fixed_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    starting_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)

    video = models.FileField(upload_to='products/videos/', blank=True, null=True)
    view_360 = models.FileField(upload_to='products/360/', blank=True, null=True)

    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    in_stock = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    enquiry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            i = 1
            while Product.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{i}"
                i += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"

    def get_price_display(self):
        if self.price_style == 'fixed' and self.fixed_price:
            return f"₹{self.fixed_price:,.0f}"
        elif self.price_style == 'starting' and self.starting_price:
            return f"Starting from ₹{self.starting_price:,.0f}"
        elif self.price_style == 'offer':
            return "Special Offer"
        elif self.price_style == 'request':
            return "Price on Request"
        else:
            return "Call for Price"


# MULTIPLE IMAGES — DIRECTLY INSIDE PRODUCT (BEST WAY!)
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    is_main = models.BooleanField(default=False)

    def __str__(self):
        return f"Image for {self.product.name}"


class Lead(models.Model):
    STATUS_CHOICES = [('new','New'),('contacted','Contacted'),('converted','Converted'),('lost','Lost')]
    SOURCE_CHOICES = [('whatsapp','WhatsApp'),('form','Form'),('call','Call')]

    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='leads')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='form')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} → {self.store.name}"