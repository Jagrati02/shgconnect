from django import forms


class PlaceOrderForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class':       'qty-input',
            'placeholder': 'Enter quantity',
            'id':          'quantity',
            'name':        'quantity',
        })
    )