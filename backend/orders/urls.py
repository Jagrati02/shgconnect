from django.urls import path
from .views import (
    place_order,
    my_orders,
    order_detail,
    cancel_order,
    reorder,
    add_review,
    shg_orders_dashboard,
    update_order_status,
)

urlpatterns = [
    # Buyer
    path('place/<int:pk>/',        place_order,          name='place_order'),
    path('',                       my_orders,            name='my_orders'),
    path('<int:pk>/',              order_detail,         name='order_detail'),
    path('<int:pk>/cancel/',       cancel_order,         name='cancel_order'),
    path('<int:pk>/reorder/',      reorder,              name='reorder'),
    path('item/<int:pk>/review/',  add_review,           name='add_review'),

    # SHG
    path('shg/',                          shg_orders_dashboard, name='shg_orders_dashboard'),
    path('shg/update/<int:order_id>/',    update_order_status,  name='update_order_status'),
]