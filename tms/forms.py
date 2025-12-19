# tms/forms.py → FINAL FIXED & PROFESSIONAL VERSION (NO ERROR!)
from django import forms
from .models import Product, Store, StoreBanner,Category,ProductSpecification,SiteSettings,SocialLink

class EnquiryForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Name'})
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Phone'})
    )
    city = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your City'})
    )

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

# tms/forms.py → FINAL CLEAN VERSION (NO ERROR!)

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
    admin_username = forms.CharField(max_length=150)
    admin_password = forms.CharField(widget=forms.PasswordInput())

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


# tms/forms.py → ONLY THIS ONE StoreBannerForm
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