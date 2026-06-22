from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import SHGCluster, SHGClusterMember, ClusterOrder, ClusterOrderAllocation
from .allocation import allocate_order


def cluster_list(request):
    """
    Public page — shows all 10 clusters with stats.
    Accessible from the marketplace and home page.
    """
    clusters = SHGCluster.objects.all().order_by('label')
    # Stats for the page header
    total_shgs     = sum(c.total_shgs for c in clusters)
    total_states   = SHGClusterMember.objects.values('state').distinct().count()
    total_capacity = sum(c.total_capacity for c in clusters)

    context = {
        'clusters':       clusters,
        'total_shgs':     total_shgs,
        'total_states':   total_states,
        'total_capacity': total_capacity,
    }
    return render(request, 'clusters/cluster_list.html', context)


def cluster_detail(request, label):
    """
    Detail page for one cluster — shows member SHGs,
    state distribution, and livelihood breakdown.
    """
    cluster = get_object_or_404(SHGCluster, label=label)
    members = SHGClusterMember.objects.filter(cluster=cluster)

    # State breakdown
    from django.db.models import Count
    state_dist = (
        members.values('state')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Livelihood breakdown
    livelihood_dist = (
        members.values('primary_livelihood')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # District breakdown
    district_dist = (
        members.values('district')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    # Capacity stats
    from django.db.models import Avg, Sum
    stats = members.aggregate(
        avg_members = Avg('active_members'),
        avg_savings = Avg('savings_amount'),
        total_cap   = Sum('active_members'),
    )

    context = {
        'cluster':        cluster,
        'members':        members[:50],   # show first 50 in table
        'total_members':  members.count(),
        'state_dist':     state_dist,
        'livelihood_dist': livelihood_dist,
        'district_dist':  district_dist,
        'avg_members':    round(stats['avg_members'] or 0, 1),
        'avg_savings':    round(stats['avg_savings'] or 0, 1),
        'total_capacity': stats['total_cap'] or 0,
    }
    return render(request, 'clusters/cluster_detail.html', context)


@login_required
def my_cluster(request):
    """
    Shows the cluster info for the logged-in SHG user.
    Redirects buyers to cluster_list.
    """
    if not hasattr(request.user, 'shgprofile'):
        return render(request, 'clusters/cluster_list.html', {
            'clusters': SHGCluster.objects.all(),
            'message': 'Cluster information is available for SHG members only.'
        })

    shg = request.user.shgprofile

    # Try to find this SHG's cluster membership
    try:
        membership = SHGClusterMember.objects.get(shg_profile=shg)
        cluster    = membership.cluster
    except SHGClusterMember.DoesNotExist:
        # SHG exists in DB but not yet assigned to a cluster
        cluster    = None
        membership = None

    # Sibling SHGs in same cluster and state
    siblings = []
    if cluster:
        siblings = SHGClusterMember.objects.filter(
            cluster=cluster,
            state=shg.state,
        ).exclude(shg_profile=shg)[:10]

    context = {
        'shg':        shg,
        'cluster':    cluster,
        'membership': membership,
        'siblings':   siblings,
    }
    return render(request, 'clusters/my_cluster.html', context)


def allocation_plan(request, product_id):
    """
    Proportional Allocation Framework (paper Section 6, Algorithm 2).

    Computes — without placing any order or touching stock — how a bulk order
    of `quantity` units for the given product would be distributed across the
    matching livelihood cluster, using direct or proportional capacity-based
    allocation. Read-only preview reached from the place-order page.
    """
    from products.models import Product

    product = get_object_or_404(Product, pk=product_id, is_active=True)

    # Desired bulk quantity from the query string; sensible default otherwise.
    try:
        quantity = int(request.GET.get('quantity', product.min_order_qty or 1))
    except (ValueError, TypeError):
        quantity = product.min_order_qty or 1
    quantity = max(quantity, 1)

    result = allocate_order(product, quantity)

    context = {
        'product': product,
        'plan':    result,
    }
    return render(request, 'clusters/allocation_plan.html', context)


@login_required
def place_cluster_order(request, product_id):
    """
    Commit a bulk order through the Proportional Allocation Framework.

    Runs the same allocation engine as the preview, then persists the result as
    a ClusterOrder with one ClusterOrderAllocation per participating SHG. Does
    NOT touch the existing orders.Order flow or product stock — a cluster order
    is a coordinated production commitment across many SHGs, distinct from the
    single-product marketplace stock.
    """
    from products.models import Product

    product = get_object_or_404(Product, pk=product_id, is_active=True)

    if request.method != 'POST':
        return redirect('allocation_plan', product_id=product_id)

    try:
        quantity = int(request.POST.get('quantity', product.min_order_qty or 1))
    except (ValueError, TypeError):
        quantity = product.min_order_qty or 1
    quantity = max(quantity, 1)

    plan = allocate_order(product, quantity)

    if plan['error'] or not plan['allocations']:
        messages.error(
            request,
            plan['error'] or 'No cluster allocation could be computed for this order.')
        return redirect('allocation_plan', product_id=product_id)

    with transaction.atomic():
        order = ClusterOrder.objects.create(
            buyer              = request.user,
            product            = product,
            product_name       = product.name,
            cluster            = plan['cluster'],
            livelihood         = plan['livelihood'] or '',
            quantity           = quantity,
            fulfilled_quantity = plan['fulfilled'],
            mode               = plan['mode'],
            partner_count      = plan['partner_count'],
            status             = 'PENDING',
        )
        ClusterOrderAllocation.objects.bulk_create([
            ClusterOrderAllocation(
                cluster_order      = order,
                member             = a['member'],
                shg_name           = a['member'].shg_name,
                state              = a['member'].state,
                district           = a['member'].district,
                capacity           = a['capacity'],
                allocated_quantity = a['allocated'],
                share_pct          = a['share_pct'],
            )
            for a in plan['allocations']
        ])

    messages.success(
        request,
        f'Cluster order placed — {plan["fulfilled"]} units distributed across '
        f'{plan["partner_count"]} SHGs in {plan["cluster"].name}.')
    return redirect('cluster_order_detail', pk=order.pk)


@login_required
def cluster_order_detail(request, pk):
    """Detail page for one cluster order and its per-SHG allocations."""
    order = get_object_or_404(ClusterOrder, pk=pk, buyer=request.user)
    return render(request, 'clusters/cluster_order_detail.html', {
        'order':       order,
        'allocations': order.allocations.all(),
    })


@login_required
def my_cluster_orders(request):
    """List the logged-in buyer's cluster orders."""
    orders = ClusterOrder.objects.filter(buyer=request.user)
    return render(request, 'clusters/my_cluster_orders.html', {'orders': orders})
