from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Sum
from .models import Order, OrderItem
from products.models import Product
from users.models import SHGProfile
from .forms import PlaceOrderForm


# ─────────────────────────────────────────
# Place Order
# ─────────────────────────────────────────

@login_required
def place_order(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)

    # Prevent SHG from ordering their own product
    if hasattr(request.user, 'shgprofile') and product.shg == request.user.shgprofile:
        messages.error(request, 'You cannot order your own product.')
        return redirect('product_detail', pk=pk)

    if request.method == 'POST':
        form = PlaceOrderForm(request.POST)

        if form.is_valid():
            quantity = form.cleaned_data['quantity']

            min_qty = product.min_order_qty or 1

            if quantity < min_qty:
                form.add_error('quantity', f'Minimum order quantity is {min_qty}.')
            elif quantity > product.quantity_available:
                form.add_error('quantity', f'Only {product.quantity_available} units available.')
            else:
                total_price = product.price * quantity

                order = Order.objects.create(
                    buyer=request.user,
                    shg=product.shg.user,       # shg FK stores the SHG's User
                    total_price=total_price,
                    order_status='PENDING',
                    payment_status='PENDING',
                )

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                )

                # Reduce stock
                product.quantity_available -= quantity
                product.save()

                messages.success(request, 'Order placed successfully!')
                return redirect('my_orders')
    else:
        # Pre-fill with minimum order quantity
        initial_qty = product.min_order_qty or 1
        form = PlaceOrderForm(initial={'quantity': initial_qty})

    return render(request, 'place_order.html', {
        'product': product,
        'form':    form,
    })


# ─────────────────────────────────────────
# My Orders (Buyer)
# ─────────────────────────────────────────

@login_required
def my_orders(request):
    orders = Order.objects.filter(
        buyer=request.user
    ).prefetch_related('items__product__shg').order_by('-order_date')

    # Summary counts
    total_orders     = orders.count()
    pending_orders   = orders.filter(order_status='PENDING').count()
    delivered_orders = orders.filter(order_status='DELIVERED').count()
    in_transit       = orders.filter(order_status='SHIPPED').count()
    total_value      = orders.aggregate(t=Sum('total_price'))['t'] or 0

    # Paginate
    paginator   = Paginator(orders, 5)
    page        = request.GET.get('page')
    orders_page = paginator.get_page(page)

    context = {
        'orders':           orders_page,   # paginated object
        'total_orders':     total_orders,
        'pending_orders':   pending_orders,
        'delivered_orders': delivered_orders,
        'in_transit':       in_transit,
        'total_value':      total_value,
    }
    return render(request, 'orders/my_orders.html', context)


# ─────────────────────────────────────────
# Order Detail
# ─────────────────────────────────────────

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, buyer=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})


# ─────────────────────────────────────────
# Cancel Order
# ─────────────────────────────────────────

@login_required
def cancel_order(request, pk):
    order = get_object_or_404(Order, pk=pk, buyer=request.user)

    if order.order_status != 'PENDING':
        messages.error(request, 'Only pending orders can be cancelled.')
        return redirect('my_orders')

    if request.method == 'POST':
        # Restore stock
        for item in order.items.all():
            item.product.quantity_available += item.quantity
            item.product.save()

        order.order_status = 'CANCELLED'
        order.save()
        messages.success(request, 'Order cancelled successfully.')

    return redirect('my_orders')


# ─────────────────────────────────────────
# Reorder
# ─────────────────────────────────────────

@login_required
def reorder(request, pk):
    old_order = get_object_or_404(Order, pk=pk, buyer=request.user)

    # Check stock for all items before creating new order
    for item in old_order.items.all():
        if item.product.quantity_available < item.quantity:
            messages.error(
                request,
                f'Not enough stock for {item.product.name}. '
                f'Only {item.product.quantity_available} units available.'
            )
            return redirect('my_orders')

    new_order = Order.objects.create(
        buyer=request.user,
        shg=old_order.shg,
        total_price=old_order.total_price,
        order_status='PENDING',
        payment_status='PENDING',
    )

    for item in old_order.items.all():
        OrderItem.objects.create(
            order=new_order,
            product=item.product,
            quantity=item.quantity,
            price=item.price,
        )
        # Reduce stock
        item.product.quantity_available -= item.quantity
        item.product.save()

    messages.success(request, 'Reorder placed successfully!')
    return redirect('my_orders')


# ─────────────────────────────────────────
# Add Review
# ─────────────────────────────────────────

@login_required
def add_review(request, pk):
    # pk here is OrderItem pk
    order_item = get_object_or_404(OrderItem, pk=pk, order__buyer=request.user)

    # Only allow review on delivered orders
    if order_item.order.order_status != 'DELIVERED':
        messages.error(request, 'You can only review delivered orders.')
        return redirect('my_orders')

    if request.method == 'POST':
        rating  = request.POST.get('rating', 0)
        comment = request.POST.get('body', '')
        try:
            order_item.review_rating  = int(rating)
            order_item.review_comment = comment
            order_item.save()
            messages.success(request, 'Review submitted successfully.')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid rating value.')

        return redirect('order_detail', pk=order_item.order.pk)

    return render(request, 'add_review.html', {'order_item': order_item})


# ─────────────────────────────────────────
# SHG Order Panel
# ─────────────────────────────────────────

@login_required
def shg_orders_dashboard(request):
    if not hasattr(request.user, 'shgprofile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    # Orders where shg = current user (User FK)
    orders = Order.objects.filter(
        shg=request.user
    ).prefetch_related('items__product').order_by('-order_date')

    context = {
        'orders':           orders,
        'total_orders':     orders.count(),
        'pending':          orders.filter(order_status='PENDING').count(),
        'confirmed':        orders.filter(order_status='CONFIRMED').count(),
        'shipped':          orders.filter(order_status='SHIPPED').count(),
        'delivered':        orders.filter(order_status='DELIVERED').count(),
        'cancelled':        orders.filter(order_status='CANCELLED').count(),
        'total_revenue':    orders.filter(
                                order_status='DELIVERED'
                            ).aggregate(t=Sum('total_price'))['t'] or 0,
    }
    return render(request, 'orders/shg_order_panel.html', context)


# ─────────────────────────────────────────
# Update Order Status (SHG action)
# ─────────────────────────────────────────

@login_required
def update_order_status(request, order_id):
    if not hasattr(request.user, 'shgprofile'):
        messages.error(request, 'Access denied.')
        return redirect('home')

    order = get_object_or_404(Order, pk=order_id, shg=request.user)

    if request.method == 'POST':
        new_status = request.POST.get('status', '')

        valid_transitions = {
            'PENDING':   ['CONFIRMED', 'CANCELLED'],
            'CONFIRMED': ['SHIPPED',   'CANCELLED'],
            'SHIPPED':   ['DELIVERED'],
        }

        if new_status in valid_transitions.get(order.order_status, []):
            order.order_status = new_status
            order.save()
            messages.success(request, f'Order marked as {new_status.lower()}.')
        else:
            messages.error(request, 'Invalid status transition.')

    return redirect('shg_orders_dashboard')