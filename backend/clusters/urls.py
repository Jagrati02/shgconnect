from django.urls import path
from .views import cluster_list, cluster_detail, my_cluster

urlpatterns = [
    path('',              cluster_list,   name='cluster_list'),
    path('<int:label>/',  cluster_detail, name='cluster_detail'),
    path('mine/',         my_cluster,     name='my_cluster'),
]