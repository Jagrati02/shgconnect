from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import SHGCluster, SHGClusterMember


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
