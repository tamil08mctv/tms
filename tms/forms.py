# tms/forms.py → FINAL PROFESSIONAL VERSION
from django import forms
from .models import Product, Store

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
    class Meta:
        model = Product
        exclude = ['store', 'slug', 'views_count', 'enquiry_count', 'created_at']
        widgets = {
            'short_desc': forms.Textarea(attrs={'rows': 3}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'deal_end_date': forms.DateInput(attrs={'type': 'date'}),
        }

# MAIN FORM FOR CREATE STORE (WITH ADMIN CREDENTIALS)
class StoreForm(forms.ModelForm):
    admin_username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. tms_chennai_admin'})
    )
    admin_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Strong password'})
    )

    class Meta:
        model = Store
        exclude = ['slug', 'created_by', 'created_at']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'working_hours': forms.TextInput(attrs={'placeholder': '10 AM - 9 PM', 'class': 'form-control'}),
            'facebook': forms.URLInput(attrs={'placeholder': 'https://facebook.com/...', 'class': 'form-control'}),
            'instagram': forms.URLInput(attrs={'placeholder': 'https://instagram.com/...', 'class': 'form-control'}),
            'youtube': forms.URLInput(attrs={'placeholder': 'https://youtube.com/...', 'class': 'form-control'}),
            'map_link': forms.URLInput(attrs={'placeholder': 'Google Maps Link', 'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'banner': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Store Name',
            'city': 'City',
            'phone': 'Phone Number',
            'whatsapp': 'WhatsApp Number',
            'email': 'Email Address',
        }

# FORM FOR EDIT STORE (NO ADMIN PASSWORD)
class StoreUpdateForm(forms.ModelForm):
    class Meta:
        model = Store
        exclude = ['slug', 'created_by', 'created_at']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'working_hours': forms.TextInput(attrs={'class': 'form-control'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control'}),
            'youtube': forms.URLInput(attrs={'class': 'form-control'}),
            'map_link': forms.URLInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'banner': forms.FileInput(attrs={'class': 'form-control'}),
        }