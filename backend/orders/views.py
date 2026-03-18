from django.shortcuts import render, redirect
from .models import Order, OrderItem
from products.models import Product
from django.contrib.auth.decorators import login_required
# Create your views here.

@login_required
def place_order(request):
    if request.method == 'POST':
        product_id = request.POST['product_id']
        quantity = int(request.POST['quantity'])
        product = Product.objects.get(id=product_id)
        order = Order(user=request.user)
        order.save()
        order_item = OrderItem(order=order, product=product, quantity=quantity)
        order_item.save()
        return redirect('home')
    products = Product.objects.all()
    return render(request, 'place_order.html', {'products': products})

def order_history(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'order_history.html', {'orders': orders})

def my_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'my_orders.html', {'orders': orders})


