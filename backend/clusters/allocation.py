"""
Proportional Capacity-Based Order Allocation.

Implements the allocation framework described in Section 6 (Algorithm 2)
of the SahayogBazaar paper. Given a bulk order for a product of category P
and quantity Q, the framework:

    1. Routes the order to the cluster whose dominant livelihood matches P.
    2. If a single SHG in that cluster has capacity Ci >= Q, assigns the
       full order to it (Direct Allocation) — minimising coordination overhead.
    3. Otherwise distributes Q proportionally to capacity:
           Ai = (Ci / Ctotal) * Q,     with   sum(Ai) = Q.

Capacity Ci is the SHG's active member count. This is the same capacity
feature used during clustering — SHGCluster.total_capacity is defined as the
sum of member counts (see clusters/management/commands/import_clusters.py).

This module performs read-only computation and does NOT modify any order,
product, or stock records. It is consumed by the allocation_plan view.
"""

from .models import SHGCluster, SHGClusterMember


# Size of the partner coordination group an order is distributed across.
# The matching cluster can hold tens of thousands of SHGs nationally; a real
# bulk order is fulfilled by a tractable group of high-capacity partners in
# the same state. The proportional formula is applied exactly over this set,
# so the displayed allocations always sum to Q.
WORKING_SET_SIZE = 25


# ── Product category P -> cluster livelihood mapping ──────────────
# Keys are substrings searched (case-insensitive) in the product's category
# name, tags, and the owning SHG's product_category. Values are the
# livelihood labels stored on SHGCluster.primary_livelihood.
LIVELIHOOD_KEYWORDS = [
    ('livestock',        ['livestock', 'dairy', 'milk', 'poultry', 'egg',
                          'goat', 'wool', 'leather', 'meat', 'cattle']),
    ('agriculture',      ['agriculture', 'agri', 'crop', 'farm', 'rice',
                          'wheat', 'pulse', 'grain', 'cereal', 'vegetable',
                          'paddy', 'millet']),
    ('horticulture',     ['horticulture', 'fruit', 'flower', 'floral',
                          'medicinal', 'herb', 'orchard']),
    ('fishery',          ['fishery', 'fish', 'seafood', 'aqua', 'prawn']),
    ('custom_hiring',    ['custom_hiring', 'hiring', 'rental', 'rent',
                          'equipment', 'tractor', 'thresher', 'machinery']),
    ('live_aggregation', ['aggregation', 'aggregate', 'logistics',
                          'collection', 'dispatch']),
    ('trading',          ['trading', 'trade', 'retail', 'wholesale',
                          'commodity', 'commerce']),
    ('services',         ['services', 'service', 'tailoring', 'tailor',
                          'beauty', 'repair', 'education', 'stitching']),
    ('manufacturing',    ['manufacturing', 'manufacture', 'handicraft',
                          'craft', 'textile', 'cloth', 'fabric', 'handloom',
                          'soap', 'candle', 'pickle', 'jam', 'snack',
                          'packaged', 'processed', 'food product', 'pottery']),
]


def resolve_livelihood(product):
    """
    Resolve the livelihood label (the 'P' in Algorithm 2) for a product by
    scanning its category name, tags, and the owning SHG's product_category.
    Returns a livelihood string, or None if nothing matches.
    """
    haystack_parts = []
    if product.category and product.category.name:
        haystack_parts.append(product.category.name)
    if product.tags:
        haystack_parts.append(product.tags)
    if product.shg and product.shg.product_category:
        haystack_parts.append(product.shg.product_category)
    haystack = ' '.join(haystack_parts).lower()

    if not haystack.strip():
        return None

    for livelihood, keywords in LIVELIHOOD_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return livelihood
    return None


def route_to_cluster(product):
    """
    Algorithm 2, step 1 — identify cluster C* whose dominant livelihood
    matches the product category P. Returns (cluster, livelihood) or
    (None, livelihood) if no cluster matches the resolved livelihood.
    """
    livelihood = resolve_livelihood(product)
    if not livelihood:
        return None, None

    cluster = SHGCluster.objects.filter(
        primary_livelihood=livelihood
    ).order_by('-total_shgs').first()
    return cluster, livelihood


def _candidate_members(cluster, state=None):
    """
    Build the partner coordination group for a cluster.

    Preference is given to SHGs in the same state as the product (geographic
    coherence — the 'nearby partner SHGs' surfaced in the UI). If too few
    same-state partners exist, fall back to the whole cluster. Members are
    ranked by capacity (active_members) and capped at WORKING_SET_SIZE.
    Only members with positive capacity participate.
    """
    base = SHGClusterMember.objects.filter(cluster=cluster, active_members__gt=0)

    members = []
    if state:
        members = list(
            base.filter(state__iexact=state).order_by('-active_members')[:WORKING_SET_SIZE]
        )

    if len(members) < 2:
        members = list(base.order_by('-active_members')[:WORKING_SET_SIZE])

    return members


def _proportional_split(capacities, quantity):
    """
    Distribute `quantity` across `capacities` proportionally:
        Ai = (Ci / Ctotal) * Q.
    Uses the largest-remainder method so allocations are whole units and
    sum exactly to `quantity`.

    Callers pass the *fulfillable* quantity (min(Q, Ctotal)). This keeps every
    allocation within the SHG's own capacity: when Q >= Ctotal each SHG is
    assigned its full capacity Ci and the split sums to Ctotal; when Q < Ctotal
    the split sums to Q (guaranteeing sum(Ai) = Q, per Eq. 5).
    """
    total = sum(capacities)
    if total <= 0:
        return [0] * len(capacities)

    raw    = [c / total * quantity for c in capacities]
    floors = [int(r) for r in raw]
    leftover = quantity - sum(floors)

    # Hand out the remaining units to the largest fractional remainders.
    remainders = sorted(
        range(len(capacities)),
        key=lambda i: raw[i] - floors[i],
        reverse=True,
    )
    for i in range(leftover):
        floors[remainders[i % len(floors)]] += 1

    return floors


def allocate_order(product, quantity):
    """
    Run the full proportional allocation framework for a product and quantity.

    Returns a result dict consumed by the template:
        {
          'livelihood', 'cluster', 'quantity',
          'mode'          : 'direct' | 'proportional' | None,
          'total_capacity', 'fulfilled', 'fulfilment_ratio', 'fully_fulfilled',
          'state', 'partner_count', 'capped',
          'allocations'   : [ {member, capacity, allocated, share_pct}, ... ],
          'error'         : str | None,
        }
    """
    result = {
        'livelihood':       None,
        'cluster':          None,
        'quantity':         quantity,
        'mode':             None,
        'total_capacity':   0,
        'fulfilled':        0,
        'fulfilment_ratio': 0,
        'fully_fulfilled':  False,
        'state':            product.shg.state if product.shg else None,
        'partner_count':    0,
        'capped':           False,
        'allocations':      [],
        'error':            None,
    }

    # Step 1 — route the order to a matching cluster.
    cluster, livelihood = route_to_cluster(product)
    result['livelihood'] = livelihood
    result['cluster']    = cluster

    if cluster is None:
        result['error'] = (
            'No livelihood cluster matches this product category, so the '
            'order cannot be routed for cluster-based allocation.'
        )
        return result

    # Step 2 — retrieve the partner SHGs in the matching cluster.
    members = _candidate_members(cluster, state=result['state'])
    if not members:
        result['error'] = 'No SHGs with available capacity were found in this cluster.'
        return result

    result['partner_count'] = len(members)
    result['capped']        = len(members) >= WORKING_SET_SIZE

    capacities = [m.active_members for m in members]
    total_cap  = sum(capacities)
    result['total_capacity']   = total_cap
    result['fulfilled']        = min(quantity, total_cap)
    result['fulfilment_ratio'] = round(result['fulfilled'] / quantity, 4) if quantity else 0
    result['fully_fulfilled']  = total_cap >= quantity

    # Steps 3-4 — Direct Allocation: a single SHG can absorb the whole order.
    direct = next((m for m in members if m.active_members >= quantity), None)
    if direct is not None:
        result['mode'] = 'direct'
        result['allocations'] = [{
            'member':    direct,
            'capacity':  direct.active_members,
            'allocated': quantity,
            'share_pct': 100.0,
        }]
        return result

    # Steps 6-9 — Proportional Cluster Allocation.
    # Distribute the fulfillable quantity so no SHG is allocated beyond its
    # own capacity; when Q exceeds Ctotal the cluster fills to capacity.
    result['mode'] = 'proportional'
    splits = _proportional_split(capacities, result['fulfilled'])
    for m, cap, alloc in zip(members, capacities, splits):
        result['allocations'].append({
            'member':    m,
            'capacity':  cap,
            'allocated': alloc,
            'share_pct': round(cap / total_cap * 100, 1) if total_cap else 0,
        })

    return result
