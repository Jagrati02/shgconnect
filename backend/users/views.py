from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F
from django.utils import timezone
from .models import SHGProfile, BuyerProfile


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def is_shg(user):
    return hasattr(user, 'shgprofile')

def is_buyer(user):
    return hasattr(user, 'buyerprofile')


def _time_of_day():
    h = timezone.localtime().hour
    return 'morning' if h < 12 else 'afternoon' if h < 17 else 'evening'


def _monthly_series(orders, year):
    """Return (revenue_by_month, count_by_month) — 12-element lists for `year`."""
    revenue = [0.0] * 12
    counts  = [0] * 12
    for o in orders:
        d = timezone.localtime(o.order_date)
        if d.year == year:
            i = d.month - 1
            revenue[i] += float(o.total_price)
            counts[i]  += 1
    return [round(v, 2) for v in revenue], counts


def _pct_change(curr, prev):
    """Month-over-month percentage change, safe against a zero baseline."""
    if not prev:
        return 0
    return round((curr - prev) / prev * 100)


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

    # Booked revenue = value of all orders except cancelled ones.
    booked_orders = orders.exclude(order_status='CANCELLED')
    total_revenue = booked_orders.aggregate(t=Sum('total_price'))['t'] or 0
    avg_order_value = round(float(total_revenue) / total_orders, 2) if total_orders else 0

    # Recent orders (last 5)
    recent_orders = orders[:5]

    # Real monthly revenue / order counts for the current year (charts).
    now = timezone.localtime()
    monthly_revenue, monthly_orders = _monthly_series(booked_orders, now.year)
    m = now.month - 1
    revenue_growth = _pct_change(monthly_revenue[m], monthly_revenue[m - 1] if m else 0)
    order_growth   = _pct_change(monthly_orders[m],  monthly_orders[m - 1]  if m else 0)

    # Top products by real revenue (and order count) from this SHG's order items.
    item_rows = (
        OrderItem.objects
        .filter(order__shg=request.user)
        .exclude(order__order_status='CANCELLED')
        .values('product__name')
        .annotate(orders=Count('order', distinct=True),
                  revenue=Sum(F('quantity') * F('price')))
        .order_by('-revenue')[:5]
    )
    max_rev = max((r['revenue'] for r in item_rows), default=0) or 1
    top_products = [{
        'name':         r['product__name'],
        'total_orders': r['orders'],
        'revenue':      round(r['revenue'], 2),
        'sales_pct':    round(r['revenue'] / max_rev * 100),
    } for r in item_rows]

    # Sales-by-category (donut chart).
    cat_rows = (
        OrderItem.objects
        .filter(order__shg=request.user)
        .exclude(order__order_status='CANCELLED')
        .values('product__category__name')
        .annotate(rev=Sum(F('quantity') * F('price')))
        .order_by('-rev')[:6]
    )
    category_data  = [round(float(r['rev']), 2) for r in cat_rows]
    category_names = '|'.join((r['product__category__name'] or 'Other') for r in cat_rows)

    # Repeat buyers (analytics).
    buyer_counts    = booked_orders.values('buyer').annotate(c=Count('id'))
    distinct_buyers = len(buyer_counts)
    repeat_buyers   = sum(1 for b in buyer_counts if b['c'] > 1)
    repeat_pct      = round(repeat_buyers / distinct_buyers * 100) if distinct_buyers else 0

    # ── Cluster Network — real data from the ML cluster linkage ──
    from clusters.models import SHGClusterMember, ClusterOrder

    membership = (SHGClusterMember.objects
                  .filter(shg_profile=shg)
                  .select_related('cluster').first())
    cluster_members  = []
    cluster_size     = 0
    cluster_capacity = 0
    cluster_match_score = 0
    cluster_revenue  = 0
    cluster_orders   = 0
    if membership:
        my_cluster       = membership.cluster
        cluster_size     = my_cluster.total_shgs
        cluster_capacity = my_cluster.total_capacity
        cluster_match_score = round(my_cluster.silhouette_score * 100)
        cluster_orders   = ClusterOrder.objects.filter(cluster=my_cluster).count()

        siblings = (SHGClusterMember.objects
                    .filter(cluster=my_cluster)
                    .exclude(pk=membership.pk))
        same_state = siblings.filter(state__iexact=shg.state)
        chosen = same_state if same_state.exists() else siblings
        for mm in chosen.order_by('-active_members')[:6]:
            cluster_members.append({
                'name':            mm.shg_name,
                'district':        mm.district,
                'state':           mm.state,
                'capacity':        mm.active_members,
                'shared_products': 1,
            })

    context = {
        'shg':             shg,
        'today':           now,
        'time_of_day':     _time_of_day(),
        'product_count':   product_count,
        'draft_count':     draft_count,
        'my_products':     my_products,
        'total_orders':    total_orders,
        'pending_count':   pending_count,
        'total_revenue':   total_revenue,
        'revenue_growth':  revenue_growth,
        'order_growth':    order_growth,
        'avg_order_value': avg_order_value,
        'repeat_buyers':   repeat_buyers,
        'repeat_pct':      repeat_pct,
        'recent_orders':   recent_orders,
        'top_products':    top_products,
        'cluster_orders':  cluster_orders,
        'avg_rating':      '—',
        'review_count':    0,
        'monthly_revenue': monthly_revenue,
        'monthly_orders':  monthly_orders,
        'category_data':   category_data,
        'category_names':  category_names,
        'cluster_size':    cluster_size,
        'cluster_capacity': cluster_capacity,
        'cluster_match_score': cluster_match_score,
        'cluster_revenue': cluster_revenue,
        'cluster_members': cluster_members,
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

    from orders.models import Order, OrderItem
    from products.models import Product

    buyer  = request.user.buyerprofile
    orders = Order.objects.filter(buyer=request.user).order_by('-order_date')

    total_orders = orders.count()

    # Booked spend = value of all orders except cancelled ones.
    booked_orders = orders.exclude(order_status='CANCELLED')
    total_spent   = booked_orders.aggregate(t=Sum('total_price'))['t'] or 0
    avg_order_value = round(float(total_spent) / total_orders, 2) if total_orders else 0

    # Real monthly spend (charts) + this-month figures.
    now = timezone.localtime()
    monthly_spending, monthly_counts = _monthly_series(booked_orders, now.year)
    m = now.month - 1
    spent_this_month  = monthly_spending[m]
    orders_this_month = monthly_counts[m]
    monthly_change    = _pct_change(monthly_spending[m], monthly_spending[m - 1] if m else 0)

    active_orders  = orders.exclude(order_status__in=['DELIVERED', 'CANCELLED'])
    recent_orders  = orders[:5]

    # Distinct SHGs and states sourced from.
    shgs_supported = booked_orders.values('shg').distinct().count()
    states = set()
    for o in booked_orders.select_related('shg__shgprofile'):
        prof = getattr(o.shg, 'shgprofile', None)
        if prof and prof.state:
            states.add(prof.state)
    states_covered = len(states)

    # Reorders = orders beyond the first placed with each SHG.
    repeat_orders = total_orders - shgs_supported if total_orders > shgs_supported else 0
    repeat_pct    = round(repeat_orders / total_orders * 100) if total_orders else 0

    # Most-purchased products (analytics table).
    item_rows = (
        OrderItem.objects
        .filter(order__buyer=request.user)
        .exclude(order__order_status='CANCELLED')
        .values('product__id')
        .annotate(order_count=Count('order', distinct=True),
                  total_units=Sum('quantity'),
                  total_spent=Sum(F('quantity') * F('price')))
        .order_by('-total_spent')[:5]
    )
    prod_map = {
        p.id: p for p in Product.objects
        .filter(id__in=[r['product__id'] for r in item_rows])
        .select_related('shg', 'category')
    }
    top_purchased = [{
        'product':     prod_map[r['product__id']],
        'order_count': r['order_count'],
        'total_units': r['total_units'],
        'total_spent': round(r['total_spent'], 2),
    } for r in item_rows if r['product__id'] in prod_map]

    # Spending-by-category (donut) + top category KPI.
    cat_rows = (
        OrderItem.objects
        .filter(order__buyer=request.user)
        .exclude(order__order_status='CANCELLED')
        .values('product__category__name')
        .annotate(rev=Sum(F('quantity') * F('price')), cnt=Count('id'))
        .order_by('-rev')
    )
    category_spending_data = [round(float(r['rev']), 2) for r in cat_rows[:6]]
    category_spending_labels_str = '|'.join(
        (r['product__category__name'] or 'Other') for r in cat_rows[:6])
    if cat_rows:
        top_cat = max(cat_rows, key=lambda r: r['cnt'])
        total_items = sum(r['cnt'] for r in cat_rows)
        top_category = top_cat['product__category__name'] or 'Other'
        top_category_pct = round(top_cat['cnt'] / total_items * 100) if total_items else 0
    else:
        top_category, top_category_pct = '—', 0

    # ── Bulk / Cluster orders — real ClusterOrders placed by this buyer ──
    from clusters.models import ClusterOrder

    cluster_qs        = (ClusterOrder.objects
                         .filter(buyer=request.user)
                         .select_related('cluster', 'product'))
    bulk_orders       = list(cluster_qs[:50])
    bulk_order_count  = cluster_qs.count()
    cluster_fulfilled = cluster_qs.filter(mode='proportional').count()

    bulk_savings = 0.0
    for co in cluster_qs:
        p = co.product
        if p and p.bulk_price and p.bulk_price < p.price:
            bulk_savings += float(p.price - p.bulk_price) * co.fulfilled_quantity
    bulk_savings = round(bulk_savings, 2)

    cluster_total = total_orders + bulk_order_count
    cluster_pct   = round(bulk_order_count / cluster_total * 100) if cluster_total else 0

    context = {
        'buyer':              buyer,
        'today':              now,
        'total_orders':       total_orders,
        'orders_this_month':  orders_this_month,
        'total_spent':        total_spent,
        'avg_order_value':    avg_order_value,
        'shgs_supported':     shgs_supported,
        'states_covered':     states_covered,
        'repeat_orders':      repeat_orders,
        'repeat_pct':         repeat_pct,
        'active_orders':      active_orders,
        'recent_orders':      recent_orders,
        'wishlist_items':     [],
        'wishlist_count':     0,
        'recommended_products': [],
        'bulk_orders':        bulk_orders,
        'bulk_order_count':   bulk_order_count,
        'cluster_fulfilled':  cluster_fulfilled,
        'bulk_savings':       bulk_savings,
        'reorder_products':   [],
        'top_purchased':      top_purchased,
        'monthly_spending':   monthly_spending,
        'category_spending_data':       category_spending_data,
        'category_spending_labels_str': category_spending_labels_str,
        'alerts':             [],
        'notif_count':        0,
        'pending_orders':     orders.filter(order_status='PENDING').count(),
        'spent_this_month':   spent_this_month,
        'monthly_change':     monthly_change,
        'top_category':       top_category,
        'top_category_pct':   top_category_pct,
        'cluster_orders':     bulk_order_count,
        'cluster_pct':        cluster_pct,
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