from django.urls import path
from .views import (
    cluster_list, cluster_detail, my_cluster, allocation_plan,
    place_cluster_order, cluster_order_detail, my_cluster_orders,
)

urlpatterns = [
    path('',                            cluster_list,         name='cluster_list'),
    path('allocate/<int:product_id>/',  allocation_plan,      name='allocation_plan'),
    path('allocate/<int:product_id>/place/', place_cluster_order, name='place_cluster_order'),
    path('orders/',                     my_cluster_orders,    name='my_cluster_orders'),
    path('orders/<int:pk>/',            cluster_order_detail, name='cluster_order_detail'),
    path('mine/',                       my_cluster,           name='my_cluster'),
    path('<int:label>/',                cluster_detail,       name='cluster_detail'),
]