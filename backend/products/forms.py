from django import forms
from .models import Product, Category


class ProductForm(forms.ModelForm):
    class Meta:
        model  = Product
        # shg is set in the view, not the form
        # extra fields (unit, min_order_qty etc.) are handled manually in views
        fields = [
            'name',
            'category',
            'description',
            'price',
            'quantity_available',
            'image',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'price': forms.NumberInput(attrs={'step': '0.01'}),
        }