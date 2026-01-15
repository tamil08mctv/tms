from django.contrib.auth.models import User
from django import forms
import re
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import (
    Product, Store, StoreBanner, Category, ProductSpecification,
    SiteSettings, SocialLink, StoreAdmin, VariantAttribute,
    ProductVariant, VariantValue, VariantSpecification
)


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
            'inputmode': 'numeric'
        })
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your City'})
    )
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'style': 'display:none;'})
    )

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
        if not phone_clean:
            raise ValidationError("Phone number is required")
        if not re.match(r'^\+?\d+$', phone_clean):
            raise ValidationError("Only digits allowed")
        if len(phone_clean) < 8:
            raise ValidationError("Number too short")
        if len(phone_clean) > 15:
            raise ValidationError("Number too long")
        if 10 <= len(phone_clean) <= 11:
            if not re.match(r'^[2-9]', phone_clean):
                raise ValidationError("Invalid Indian number format")
            return '+91' + phone_clean
        if not phone_clean.startswith('+'):
            raise ValidationError("International numbers must start with +")
        return phone_clean

    def clean_city(self):
        city = self.cleaned_data['city'].strip()
        if city:
            if len(city) < 3:
                raise ValidationError("City name too short.")
            if not re.match(r'^[a-zA-Z\s\.\-]+$', city):
                raise ValidationError("Only letters and spaces allowed.")
            return city.title()
        return city

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


SocialLinkFormSet = inlineformset_factory(
    SiteSettings, SocialLink,
    fields=('platform', 'url', 'order'), extra=0, can_delete=True,
    widgets={
        'platform': forms.Select(attrs={'class': 'form-select'}),
        'url': forms.URLInput(attrs={'class': 'form-control'}),
        'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
    }
)

from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import (
    Product, ProductSpecification, VariantAttribute,
    ProductVariant, VariantValue, VariantSpecification
)

class ProductForm(forms.ModelForm):
    extra_images = forms.FileField(
        required=False,
        label="Additional Images (Multiple)",
        widget=forms.FileInput(attrs={'accept': 'image/*', 'multiple': '', 'class': 'form-control'})
    )
    video = forms.FileField(
        required=False,
        label="Product Video (optional)",
        widget=forms.FileInput(attrs={'accept': 'video/*', 'class': 'form-control'})
    )

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'short_desc', 'description',
            'regular_price', 'offer_price', 'deal_end_date',          # <--- these must stay here
            'in_stock', 'is_featured', 'is_best_seller',
            'is_limited_deal', 'is_special_offer', 'is_new_arrival',
            'call_for_price'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg'}),
            'category': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'short_desc': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'regular_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'offer_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'deal_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'in_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        has_variants = kwargs.pop('has_variants', False)
        super().__init__(*args, **kwargs)

        # Only make them read-only + placeholder when variants exist
        # But NEVER remove them from the form
        if has_variants:
            for f in ['regular_price', 'offer_price', 'deal_end_date']:
                if f in self.fields:
                    self.fields[f].required = False
                    self.fields[f].widget.attrs.update({
                        'readonly': 'readonly',
                        'class': 'form-control bg-light',  # light background to indicate disabled
                        'placeholder': 'Managed by variants'
                    })

# === Formsets ===

ProductSpecFormSet = inlineformset_factory(
    Product, ProductSpecification,
    fields=('name', 'value'),
    extra=1,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Material'}),
        'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Teak Wood'}),
    },
   
)

VariantAttributeFormSet = inlineformset_factory(
    Product, VariantAttribute,
    fields=('name',),
    extra=1,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Color, Size'})
    },
)

class ProductVariantForm(forms.ModelForm):
    extra_images = forms.FileField(
        required=False,
        label="Additional Images (Multiple)",
        widget=forms.FileInput(attrs={'accept': 'image/*', 'multiple': '', 'class': 'form-control'})
    )

    class Meta:
        model = ProductVariant
        fields = ['regular_price', 'offer_price', 'in_stock', 'image']
        widgets = {
            'regular_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'offer_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'in_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image': forms.FileInput(attrs={'class': 'form-control'})
        }


class VariantValueForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
   
        if 'instance' in kwargs and kwargs['instance'].variant:
            product = kwargs['instance'].variant.product
            self.fields['attribute'].queryset = VariantAttribute.objects.filter(product=product)
        

    class Meta:
        model = VariantValue
        fields = ('attribute', 'value')
        widgets = {
            'attribute': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Red'})
        }

class VariantValueInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)
        if self.product:
            for form in self.forms:
                form.fields['attribute'].queryset = self.product.variant_attributes.all()

def get_variant_value_formset(product=None, extra=0):
    return inlineformset_factory(
        ProductVariant, VariantValue,
        form=VariantValueForm,
        formset=VariantValueInlineFormSet,
        extra=extra,
        can_delete=True,
    )

VariantSpecFormSet = inlineformset_factory(
    ProductVariant, VariantSpecification,
    fields=('name', 'value'),
    extra=1,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Weight'}),
        'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 5 kg'})
    },
   
)

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Ex: Sofas, Beds, Dining Tables'}),
        }

class StoreForm(forms.ModelForm):
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
            user = self.instance.user
            user.username = username
            if password:  # Only update password if provided
                user.set_password(password)
            user.save()
        else:
            if not password:
                raise forms.ValidationError("Password is required for new admin.")
            user = User.objects.create_user(username=username, password=password)
            store_admin.user = user

        if commit:
            store_admin.save()
        return store_admin

