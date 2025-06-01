from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('menu/', views.menu, name='menu'),
    path('orders/', views.orders, name='orders'),
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('create-payment/', views.create_payment, name='create_payment'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('place_order/', views.place_order, name='place_order'),
    # path('admin/orders/', views.admin_orders, name='admin_orders'),
    # path('admin/menu/', views.admin_menu, name='admin_menu'),
] 