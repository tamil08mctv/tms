# tms/forms.py
from django import forms
from .models import Product, Store

class EnquiryForm(forms.Form):
    customer_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class': 'form-control'}))
    city = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}), required=False)

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        exclude = ['store', 'slug']

class StoreForm(forms.ModelForm):
    admin_username = forms.CharField(max_length=100)
    admin_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Store
        fields = '__all__'
        exclude = ['slug', 'created_by']