from django.contrib import admin
from .models import (
    SHGCluster, SHGClusterMember, ClusterOrder, ClusterOrderAllocation,
)


class ClusterOrderAllocationInline(admin.TabularInline):
    model = ClusterOrderAllocation
    extra = 0


@admin.register(ClusterOrder)
class ClusterOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'product_name', 'cluster', 'mode',
                    'partner_count', 'quantity', 'fulfilled_quantity',
                    'status', 'created_at')
    list_filter  = ('mode', 'status', 'cluster')
    search_fields = ('product_name', 'buyer__username')
    inlines = [ClusterOrderAllocationInline]


admin.site.register(SHGCluster)
admin.site.register(SHGClusterMember)
