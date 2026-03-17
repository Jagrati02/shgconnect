from django.shortcuts import render, redirect 
from .models import Product
from users.models import SHGProfile
# Create your views here.

def add_product(request):
    if request.method == 'POST':
        name = request.POST['name']
        description = request.POST['description']
        price = request.POST['price']
        shg_profile = SHGProfile.objects.get(user=request.user)
        product = Product(name=name, description=description, price=price, shg_profile=shg_profile)
        product.save()
        return redirect('home')
    return render(request, 'add_product.html')

def product_list(request):
    products = Product.objects.all()
    return render(request, 'product_list.html', {'products': products})
