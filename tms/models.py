# tms/models.py → FINAL COMPLETE VERSION
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from datetime import date
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
    def __str__(self):
        return f"{self.user.username} → {self.store.name}"

class Category(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
   

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
    PRICE_STYLE_CHOICES = [
        ('fixed', 'Fixed Price'),
        ('offer', 'Discounted Offer'),
        ('deal', 'Deal of the Day'),
        ('call', 'Call for Best Price'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, blank=True, unique=True)
    short_desc = models.TextField(max_length=500)
    description = models.TextField(blank=True)

    price_style = models.CharField(max_length=20, choices=PRICE_STYLE_CHOICES, default='offer')
    regular_price = models.DecimalField(max_digits=12, decimal_places=0)           # ← NO default!
    offer_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    discount_percent = models.PositiveIntegerField(null=True, blank=True)
    deal_end_date = models.DateField(null=True, blank=True)

    video = models.FileField(upload_to='products/videos/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    in_stock = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)
    enquiry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

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

        super().save(*args, **kwargs)

    def get_price_display(self):
        if self.price_style in ['fixed', 'offer', 'deal'] and self.offer_price:
            prefix = "Deal Price: " if self.is_deal_active() else ""
            return f"{prefix}₹{self.offer_price:,.0f}"
        return "Call for Best Price"

    def get_striked_price(self):
        if self.regular_price and self.offer_price and self.offer_price < self.regular_price:
            return f"₹{self.regular_price:,.0f}"
        return None

    def is_deal_active(self):
        return self.price_style == 'deal' and self.deal_end_date and self.deal_end_date >= date.today()

    def __str__(self):
        return f"{self.name} - {self.store.name}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/images/')
    is_main = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)  # ← ADD THIS LINE

    class Meta:
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"Image - {self.product.name}"

# models.py → ADD THIS NEW MODEL
class StoreBanner(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='banners')
    image = models.ImageField(upload_to='stores/banners/extra/')
    caption = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store.name} - Banner"

class Lead(models.Model):
    STATUS_CHOICES = [('new','New'),('contacted','Contacted'),('converted','Converted'),('lost','Lost')]
    SOURCE_CHOICES = [('whatsapp','WhatsApp'),('form','Form'),('call','Call')]
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='leads')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='form')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} → {self.store.name}"