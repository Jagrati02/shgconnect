from django.urls import path
from .views import (
    product_list,
    product_detail,
    add_product,
    edit_product,
    delete_product,
)

urlpatterns = [
    path('',                    product_list,   name='product_list'),
    path('add/',               add_product,    name='add_product'),
    path('<int:pk>/',          product_detail, name='product_detail'),
    path('<int:pk>/edit/',     edit_product,   name='edit_product'),
    path('<int:pk>/delete/',   delete_product, name='delete_product'),
]