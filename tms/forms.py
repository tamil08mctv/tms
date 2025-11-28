# tms/forms.py → FINAL FIXED & PROFESSIONAL VERSION (NO ERROR!)
from django import forms
from .models import Product, Store, StoreBanner,Category

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
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Your Message (Optional)'}), 
        required=False
    )

class ProductForm(forms.ModelForm):
    # FINAL FIX: REMOVE 'multiple=True' FROM WIDGET → IT'S NOT ALLOWED!
    # Instead, we just use normal FileInput + handle multiple files in view with getlist()
    extra_images = forms.FileField(
        required=False,
        label="Upload Additional Images (Hold Ctrl/Cmd to select multiple)",
        widget=forms.FileInput(attrs={
            'accept': 'image/*',
            'class': 'form-control'
            # DO NOT ADD 'multiple': True HERE → CAUSES CRASH!
        })
    )

    video = forms.FileField(
        required=False,
        label="Upload Product Video (MP4 recommended)",
        widget=forms.FileInput(attrs={
            'accept': 'video/*',
            'class': 'form-control'
        })
    )

    class Meta:
        model = Product
        fields = [
            'category', 'name', 'short_desc', 'description',
            'price_style', 'regular_price', 'offer_price', 'deal_end_date',
            'video', 'is_featured', 'is_new', 'in_stock'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Premium Leather Sofa'}),
            'category': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'short_desc': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 7, 'class': 'form-control'}),
            'price_style': forms.Select(attrs={'class': 'form-select'}),
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


class StoreBannerForm(forms.ModelForm):
    class Meta:
        model = StoreBanner
        fields = ['image', 'caption', 'is_active']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Optional caption'}),
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

class StoreBannerForm(forms.ModelForm):
    class Meta:
        model = StoreBanner
        fields = ['image', 'caption', 'is_active']
        widgets = {
            'caption': forms.TextInput(attrs={'placeholder': 'Optional caption'}),
        }