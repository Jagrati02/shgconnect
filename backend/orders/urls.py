from django.urls import path
from .views import place_order,order_history, my_orders

urlpatterns = [
    path('place/', place_order, name='place_order'),
    path('history/', order_history, name='order_history'),
    path('my-orders/', my_orders, name='my_orders'), 
]