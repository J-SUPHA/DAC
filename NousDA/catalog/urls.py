from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
]

urlpatterns += [
    path('export_excel/', views.export_inventory_to_excel, name='export_excel'),
]

urlpatterns += [
    path('export_csv', views.export_inventory_to_csv, name='export_csv')
]
