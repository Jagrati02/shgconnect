from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import SHGProfile, BuyerProfile


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def is_shg(user):
    return hasattr(user, 'shgprofile')

def is_buyer(user):
    return hasattr(user, 'buyerprofile')


# ─────────────────────────────────────────
# Auth views
# ─────────────────────────────────────────

def signup(request):
    if request.method == 'POST':
        first_name       = request.POST.get('first_name', '').strip()
        last_name        = request.POST.get('last_name', '').strip()
        email            = request.POST.get('email', '').strip()
        password         = request.POST.get('password1', '')
        confirm_password = request.POST.get('password2', '')
        role             = request.POST.get('role', 'buyer')
        shg_name         = request.POST.get('shg_name', '').strip()
        state            = request.POST.get('state', '').strip()
        phone            = request.POST.get('phone', '').strip()

        # Validations
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('signup')

        if User.objects.filter(username=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return redirect('signup')

        # Create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        # Create role-based profile
        if role == 'shg':
            SHGProfile.objects.create(
                user=user,
                shg_id=f'SHG{user.id}',
                shg_name=shg_name or email,
                state=state,
                phone=phone,
                members_count=1,
                product_category='General',
                production_capacity=0,
            )
        else:
            BuyerProfile.objects.create(
                user=user,
                state=state,
                phone=phone,
            )

        messages.success(request, 'Account created successfully. Please log in.')
        return redirect('login')

    return render(request, 'signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect based on role
            if is_shg(user):
                return redirect('shg_dashboard')
            elif is_buyer(user):
                return redirect('buyer_dashboard')
            return redirect('home')
        else:
            messages.error(request, 'Invalid email or password.')
            return redirect('login')

    return render(request, 'login.html')


@login_required
def dashboard(request):
    """Generic dashboard redirect based on role."""
    if is_shg(request.user):
        return redirect('shg_dashboard')
    elif is_buyer(request.user):
        return redirect('buyer_dashboard')
    messages.error(request, 'No profile found for this account.')
    return redirect('login')


# ─────────────────────────────────────────
# SHG Dashboard
# ─────────────────────────────────────────

@login_required
def shg_dashboard(request):
    if not is_shg(request.user):
        return redirect('home')

    from orders.models import Order, OrderItem
    from products.models import Product

    shg = request.user.shgprofile

    # Products
    my_products   = Product.objects.filter(shg=shg)
    product_count = my_products.filter(is_active=True).count()
    draft_count   = my_products.filter(is_active=False).count()

    # Orders (shg field on Order is a User FK)
    orders        = Order.objects.filter(shg=request.user).order_by('-order_date')
    total_orders  = orders.count()
    pending_count = orders.filter(order_status='PENDING').count()

    # Revenue
    total_revenue = orders.filter(
        order_status='DELIVERED'
    ).aggregate(t=Sum('total_price'))['t'] or 0

    # Recent orders (last 5)
    recent_orders = orders[:5]

    # Top products by order count — simple approach
    top_products = my_products.order_by('-id')[:5]

    # Monthly revenue — 12 zeros as placeholder
    # Replace with real aggregation when ready
    monthly_revenue = [0] * 12
    monthly_orders  = [0] * 12

    context = {
        'shg':             shg,
        'product_count':   product_count,
        'draft_count':     draft_count,
        'my_products':     my_products,
        'total_orders':    total_orders,
        'pending_count':   pending_count,
        'total_revenue':   total_revenue,
        'recent_orders':   recent_orders,
        'top_products':    top_products,
        'cluster_orders':  0,
        'avg_rating':      '—',
        'review_count':    0,
        'monthly_revenue': monthly_revenue,
        'monthly_orders':  monthly_orders,
        'cluster_size':    0,
        'cluster_members': [],
        'forecast_products': my_products.filter(forecast_enabled=True),
        'market_signals':  [],
        'alerts':          [],
        'dashboard_orders': orders[:20],
    }

    return render(request, 'shg_dashboard.html', context)


# ─────────────────────────────────────────
# Buyer Dashboard
# ─────────────────────────────────────────

@login_required
def buyer_dashboard(request):
    if not is_buyer(request.user):
        return redirect('home')

    from orders.models import Order

    buyer  = request.user.buyerprofile
    orders = Order.objects.filter(buyer=request.user).order_by('-order_date')

    total_orders       = orders.count()
    orders_this_month  = orders.count()   # refine with date filter when ready
    total_spent        = orders.filter(
        order_status='DELIVERED'
    ).aggregate(t=Sum('total_price'))['t'] or 0

    active_orders  = orders.exclude(
        order_status__in=['DELIVERED', 'CANCELLED']
    )
    recent_orders  = orders[:5]

    context = {
        'buyer':              buyer,
        'total_orders':       total_orders,
        'orders_this_month':  orders_this_month,
        'total_spent':        total_spent,
        'avg_order_value':    round(total_spent / total_orders, 2) if total_orders else 0,
        'shgs_supported':     orders.values('shg').distinct().count(),
        'states_covered':     0,
        'repeat_orders':      0,
        'repeat_pct':         0,
        'active_orders':      active_orders,
        'recent_orders':      recent_orders,
        'wishlist_items':     [],
        'wishlist_count':     0,
        'recommended_products': [],
        'bulk_orders':        [],
        'bulk_order_count':   0,
        'cluster_fulfilled':  0,
        'bulk_savings':       0,
        'reorder_products':   [],
        'top_purchased':      [],
        'monthly_spending':   [0] * 12,
        'alerts':             [],
        'notif_count':        0,
        'pending_orders':     orders.filter(order_status='PENDING').count(),
        'spent_this_month':   0,
        'monthly_change':     0,
        'top_category':       '—',
        'top_category_pct':   0,
        'cluster_orders':     0,
        'cluster_pct':        0,
        'women_supported':    0,
        'households_impacted': 0,
    }

    return render(request, 'buyer_dashboard.html', context)


# ─────────────────────────────────────────
# Profile update views
# ─────────────────────────────────────────

@login_required
def update_shg_profile(request):
    if request.method == 'POST':
        shg = get_object_or_404(SHGProfile, user=request.user)
        shg.shg_name  = request.POST.get('name', shg.shg_name)
        shg.reg_no    = request.POST.get('reg_no', shg.reg_no)
        shg.about     = request.POST.get('about', shg.about)
        shg.district  = request.POST.get('district', shg.district)
        shg.pin_code  = request.POST.get('pin_code', shg.pin_code)
        shg.phone     = request.POST.get('phone', shg.phone)
        shg.bank_name = request.POST.get('bank_name', shg.bank_name)
        shg.account_no = request.POST.get('account_no', shg.account_no)
        shg.ifsc      = request.POST.get('ifsc', shg.ifsc)
        shg.upi_id    = request.POST.get('upi_id', shg.upi_id)
        if 'logo' in request.FILES:
            shg.logo = request.FILES['logo']
        shg.save()
        messages.success(request, 'Profile updated successfully.')
    return redirect('shg_dashboard')


@login_required
def update_buyer_profile(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name  = request.POST.get('last_name', user.last_name)
        user.email      = request.POST.get('email', user.email)
        user.save()

        buyer = get_object_or_404(BuyerProfile, user=request.user)
        buyer.phone         = request.POST.get('phone', buyer.phone)
        buyer.company       = request.POST.get('company', buyer.company)
        buyer.gst           = request.POST.get('gst', buyer.gst)
        buyer.address_line1 = request.POST.get('address_line1', buyer.address_line1)
        buyer.address_line2 = request.POST.get('address_line2', buyer.address_line2)
        buyer.city          = request.POST.get('city', buyer.city)
        buyer.state         = request.POST.get('state', buyer.state)
        buyer.pin_code      = request.POST.get('pin_code', buyer.pin_code)
        buyer.email_orders          = 'email_orders' in request.POST
        buyer.email_recommendations = 'email_recommendations' in request.POST
        buyer.price_alerts          = 'price_alerts' in request.POST
        if 'avatar' in request.FILES:
            buyer.avatar = request.FILES['avatar']
        buyer.save()
        messages.success(request, 'Account updated successfully.')
    return redirect('buyer_dashboard')