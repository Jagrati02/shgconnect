from django.shortcuts import render
from products.models import Product, Category


def home(request):
    # Latest active products for homepage (optional future use)
    latest_products = Product.objects.filter(
        is_active=True
    ).order_by('-created_at')[:6]

    context = {
        'latest_products': latest_products,
        # features uses {% empty %} fallback in template — no need to pass
    }
    return render(request, 'home.html', context)