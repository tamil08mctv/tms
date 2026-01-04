# tms/forms.py â†’ FINAL: WITH StoreAdminForm
from django.contrib.auth.models import User
from django import forms
import re
from django.core.exceptions import ValidationError
from .models import Product, Store, StoreBanner,Category,ProductSpecification,SiteSettings,SocialLink, StoreAdmin

from django import forms

class EnquiryForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name'})
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg rounded-pill',
            'placeholder': 'Phone (e.g. 9876543210 or +919876543210)',
            'inputmode': 'numeric'  # Shows numeric keyboard on mobile
        })
    )
    city = forms.CharField(
        max_length=100, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your City'})
    )
    # Honeypot field - hidden from humans
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'style': 'display:none;'})  # Invisible
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone)

        if not phone_clean:
            raise ValidationError("Phone number is required")

        if not re.match(r'^\+?\d+$', phone_clean):
            raise ValidationError("Only digits allowed (optional + at start)")

        if len(phone_clean) < 8:
            raise ValidationError("Number too short")

        if len(phone_clean) > 15:
            raise ValidationError("Number too long")

        # Indian mobile or landline (10-11 digits)
        if 10 <= len(phone_clean) <= 11:
            if not re.match(r'^[2-9]', phone_clean):
                raise ValidationError("Invalid Indian number format")
            return '+91' + phone_clean

        # International: must have +
        if not phone_clean.startswith('+'):
            raise ValidationError("International numbers must start with +")

        return phone_clean

    def clean_city(self):
        city = self.cleaned_data['city'].strip()
        if city:
            if len(city) < 3:
                raise ValidationError("City name too short.")
            if not re.match(r'^[a-zA-Z\s\.\-]+$', city):
                raise ValidationError("City can only contain letters and spaces.")
            return city.title()
        return city  # Allow empty

    def clean_website(self):
        if self.cleaned_data['website']:
            raise ValidationError("Spam detected")
        return ''
    
class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = '__all__'
        widgets = {
            'address': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'site_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'copyright_text': forms.TextInput(attrs={'class': 'form-control'}),
        }


from django.forms import inlineformset_factory

SocialLinkFormSet = inlineformset_factory(
    SiteSettings,
    SocialLink,
    fields=('platform', 'url', 'order'),
    extra=0,
    can_delete=True,
    widgets={
        'platform': forms.Select(attrs={'class': 'form-select'}),
        'url': forms.URLInput(attrs={'class': 'form-control'}),
        'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
    }
)

# tms/forms.py â†’ FINAL CLEAN VERSION (NO ERROR!)

class ProductForm(forms.ModelForm):
    extra_images = forms.FileField(
        required=False,
        label="Upload Additional Images",
        widget=forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'})
    )

    video = forms.FileField(
        required=False,
        label="Product Video",
        widget=forms.FileInput(attrs={'accept': 'video/*', 'class': 'form-control'})
    )
    

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'short_desc', 'description',
            'regular_price', 'offer_price', 'deal_end_date',  
            'video', 'in_stock', 'is_featured',
            
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'category': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'short_desc': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 7, 'class': 'form-control'}),
            'regular_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '25000'}),
            'offer_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '19999'}),
            'deal_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ex: Sofas, Beds, Dining Tables'}),
        }

class StoreForm(forms.ModelForm):
    # â† REMOVED admin_username/admin_password - now separate

    class Meta:
        model = Store
        exclude = ['slug', 'created_by', 'created_at']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'working_hours': forms.TextInput(attrs={'placeholder': '10 AM - 9 PM'}),
        }

class StoreUpdateForm(forms.ModelForm):
    class Meta:
        model = Store
        exclude = ['slug', 'created_by', 'created_at']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }


# tms/forms.py â†’ ONLY THIS ONE StoreBannerForm
class StoreBannerForm(forms.ModelForm):
    class Meta:
        model = StoreBanner
        fields = [
            'image_desktop', 'image_tablet', 'image_mobile',
            'link', 'caption', 'is_active', 'order'
        ]
        widgets = {
            'image_desktop': forms.FileInput(attrs={'class': 'form-control'}),
            'image_tablet': forms.FileInput(attrs={'class': 'form-control'}),
            'image_mobile': forms.FileInput(attrs={'class': 'form-control'}),
            'link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https:// or /products/?filter=deals'}),
            'caption': forms.TextInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '0'}),
        }


from django.forms import inlineformset_factory

# ADD THIS AT THE BOTTOM
ProductSpecFormSet = inlineformset_factory(
    Product,
    ProductSpecification,
    fields=('name', 'value'),
    extra=5,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Material'}),
        'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Teak Wood'}),
    }
)


# Add this import at the top if not already there
from django.contrib.auth.models import User

class StoreAdminForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password (required for new admin)'}),
        required=False,
        help_text="Leave blank to keep current password"
    )

    class Meta:
        model = StoreAdmin
        fields = ['is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['username'].initial = self.instance.user.username
            self.fields['password'].help_text = "Leave blank to keep current password"

    def clean_username(self):
        username = self.cleaned_data['username']
        # Check if username exists (excluding current user if editing)
        if self.instance.pk:
            if User.objects.exclude(pk=self.instance.user.pk).filter(username=username).exists():
                raise forms.ValidationError("This username is already taken. Please choose another.")
        else:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("This username is already taken. Please choose another.")
        return username

    def save(self, commit=True):
        store_admin = super().save(commit=False)
        username = self.cleaned_data['username']
        password = self.cleaned_data.get('password')

        if self.instance.pk:
            # Editing existing admin
            user = self.instance.user
            user.username = username
            if password:  # Only update password if provided
                user.set_password(password)
            user.save()
        else:
            # Creating new admin
            if not password:
                raise forms.ValidationError("Password is required for new admin.")
            user = User.objects.create_user(username=username, password=password)
            store_admin.user = user

        if commit:
            store_admin.save()
        return store_admin