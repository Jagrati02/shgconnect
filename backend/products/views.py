from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Product, Category
from .forms import ProductForm


# ─────────────────────────────────────────
# Product List
# ─────────────────────────────────────────

def product_list(request):
    products = Product.objects.filter(is_active=True).select_related('shg', 'category')

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(name__icontains=q)

    # Category filter
    category = request.GET.get('category', '')
    if category:
        products = products.filter(category__id=category)

    # State filter
    state = request.GET.get('state', '')
    if state:
        products = products.filter(shg__state=state)

    # Sort
    sort = request.GET.get('sort', '')
    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-created_at')

    # Paginate
    paginator = Paginator(products, 12)
    page      = request.GET.get('page')
    products  = paginator.get_page(page)

    categories = Category.objects.all()

    context = {
        'products':   products,
        'categories': categories,
        'states':     [],   # pass list of (code, name) tuples if needed
    }
    return render(request, 'product_list.html', context)


# ─────────────────────────────────────────
# Product Detail
# ─────────────────────────────────────────

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)

    # Related products — same category, exclude current
    related_products = Product.objects.filter(
        is_active=True
    ).exclude(pk=pk)

    if product.category:
        related_products = related_products.filter(category=product.category)

    related_products = related_products[:4]

    # Check if logged-in buyer has a delivered order for this product
    user_can_review = False
    order_pk = None
    if request.user.is_authenticated:
        from orders.models import Order, OrderItem
        delivered_item = OrderItem.objects.filter(
            product=product,
            order__buyer=request.user,
            order__order_status='DELIVERED'
        ).first()
        if delivered_item:
            user_can_review = not bool(delivered_item.review_rating)
            order_pk = delivered_item.pk

    context = {
        'product':          product,
        'related_products': related_products,
        'reviews':          [],      # no Review model yet — empty list
        'user_can_review':  user_can_review,
        'order_pk':         order_pk,
    }
    return render(request, 'product_detail.html', context)


# ─────────────────────────────────────────
# Add Product
# ─────────────────────────────────────────

@login_required
def add_product(request):
    # Only SHG users can add products
    if not hasattr(request.user, 'shgprofile'):
        messages.error(request, 'Only SHG members can list products.')
        return redirect('home')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product      = form.save(commit=False)
            product.shg  = request.user.shgprofile

            # Handle action (publish or draft)
            action = request.POST.get('action', 'publish')
            product.is_active = (action == 'publish')

            # Extra fields not in ProductForm
            product.unit           = request.POST.get('unit', '')
            product.min_order_qty  = request.POST.get('min_order_qty') or None
            product.lead_time_days = request.POST.get('lead_time_days') or None
            product.bulk_price     = request.POST.get('bulk_price') or None
            product.cluster_enabled  = 'cluster_enabled' in request.POST
            product.forecast_enabled = 'forecast_enabled' in request.POST
            product.tags           = request.POST.get('tags', '')
            product.save()

            messages.success(request, f'Product {"published" if product.is_active else "saved as draft"} successfully.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm()

    categories = Category.objects.all()
    context = {
        'form':       form,
        'categories': categories,
        'states':     [],
    }
    return render(request, 'add_product.html', context)


# ─────────────────────────────────────────
# Edit Product
# ─────────────────────────────────────────

@login_required
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    # Only the owning SHG can edit
    if not hasattr(request.user, 'shgprofile') or product.shg != request.user.shgprofile:
        messages.error(request, 'You do not have permission to edit this product.')
        return redirect('product_list')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save(commit=False)

            action = request.POST.get('action', 'publish')
            if action == 'publish':
                product.is_active = True
            elif action == 'draft':
                product.is_active = False
            elif action == 'unpublish':
                product.is_active = False

            # Extra fields
            product.unit           = request.POST.get('unit', product.unit)
            product.min_order_qty  = request.POST.get('min_order_qty') or product.min_order_qty
            product.lead_time_days = request.POST.get('lead_time_days') or product.lead_time_days
            product.bulk_price     = request.POST.get('bulk_price') or product.bulk_price
            product.cluster_enabled  = 'cluster_enabled' in request.POST
            product.forecast_enabled = 'forecast_enabled' in request.POST
            product.tags           = request.POST.get('tags', product.tags)
            product.save()

            messages.success(request, 'Product updated successfully.')
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    categories = Category.objects.all()
    context = {
        'form':       form,
        'product':    product,
        'categories': categories,
        'states':     [],
    }
    return render(request, 'edit_product.html', context)


# ─────────────────────────────────────────
# Delete Product
# ─────────────────────────────────────────

@login_required
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if not hasattr(request.user, 'shgprofile') or product.shg != request.user.shgprofile:
        messages.error(request, 'You do not have permission to delete this product.')
        return redirect('product_list')

    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully.')
        return redirect('product_list')

    return render(request, 'delete_product.html', {'product': product})