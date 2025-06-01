from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from .models import Category, MenuItem, Order, OrderItem
from .payment import create_payment_intent, handle_webhook

# def is_admin(user):
#     return user.is_authenticated and user.userprofile.is_admin

def is_admin(request):
    user = request
    print(user)
    if user.is_authenticated:
        if user.userprofile.is_admin:
            return redirect('admin_dashboard')  # or use reverse('admin_dashboard')
        else:
            return redirect('menu')  # or any normal user page
    return redirect('login')  # fallback


def home(request):
    categories = Category.objects.all()[:6]
    featured_items = MenuItem.objects.filter(is_available=True)[:6]
    context = {
        'categories': categories,
        'featured_items': featured_items,
    }
    return render(request, 'restaurant/home.html', context)

def menu(request):
    categories = Category.objects.all()
    selected_category = request.GET.get('category')
    
    if selected_category:
        menu_items = MenuItem.objects.filter(
            category__name=selected_category,
            is_available=True
        )
    else:
        menu_items = MenuItem.objects.filter(is_available=True)
    
    context = {
        'categories': categories,
        'menu_items': menu_items,
        'selected_category': selected_category,
    }
    return render(request, 'restaurant/menu.html', context)

@login_required
def orders(request):
    user_orders = Order.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'orders': user_orders,
    }
    return render(request, 'restaurant/orders.html', context)

@login_required
def place_order(request):
    if request.method == 'POST':
        cart_items = request.session.get('cart', {})
        
        if not cart_items:
            messages.error(request, 'Your cart is empty.')
            return redirect('menu')
        
        # Calculate total amount
        total_amount = 0
        for item_id, quantity in cart_items.items():
            menu_item = MenuItem.objects.get(id=item_id)
            total_amount += menu_item.price * quantity
        
        # Create order
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount,
            status='pending'
        )
        
        # Create order items
        for item_id, quantity in cart_items.items():
            menu_item = MenuItem.objects.get(id=item_id)
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=quantity,
                price_at_time_of_order=menu_item.price
            )
        
        # Clear cart
        request.session['cart'] = {}
        messages.success(request, 'Order placed successfully!')
        return redirect('orders')
    
    return redirect('menu')

@login_required
def add_to_cart(request, item_id):
    menu_item = get_object_or_404(MenuItem, id=item_id)
    cart = request.session.get('cart', {})
    
    item_id_str = str(item_id)
    if item_id_str in cart:
        cart[item_id_str] += 1
    else:
        cart[item_id_str] = 1
    
    request.session['cart'] = cart
    messages.success(request, f'{menu_item.name} added to cart.')
    return redirect('menu')

@login_required
def remove_from_cart(request, item_id):
    cart = request.session.get('cart', {})
    item_id_str = str(item_id)
    
    if item_id_str in cart:
        del cart[item_id_str]
        request.session['cart'] = cart
        messages.success(request, 'Item removed from cart.')
    
    return redirect('cart')

@login_required
def cart(request):
    cart_items = request.session.get('cart', {})
    items = []
    total = 0
    
    for item_id, quantity in cart_items.items():
        menu_item = MenuItem.objects.get(id=item_id)
        subtotal = menu_item.price * quantity
        total += subtotal
        items.append({
            'menu_item': menu_item,
            'quantity': quantity,
            'subtotal': subtotal,
        })
    
    context = {
        'cart_items': items,
        'total': total,
    }
    return render(request, 'restaurant/cart.html', context)

@user_passes_test(is_admin)
def admin_dashboard(request):
    pending_orders = Order.objects.filter(status='pending').count()
    total_sales = Order.objects.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    recent_orders = Order.objects.all().order_by('-created_at')[:10]
    
    context = {
        'pending_orders': pending_orders,
        'total_sales': total_sales,
        'recent_orders': recent_orders,
    }
    print("Admin Dashboard Context:", context)  # Debugging line
    return render(request, 'restaurant/admin_dashboard.html', context)

@user_passes_test(is_admin)
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        new_status = request.POST.get('status')
        
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            messages.success(request, f'Order #{order.id} status updated to {new_status}.')
        
    return redirect('admin_dashboard')

@login_required
def checkout(request):
    cart_items = request.session.get('cart', {})
    if not cart_items:
        return redirect('cart')
    
    # Calculate total
    total = Decimal('0.00')
    items = []
    for item_id, quantity in cart_items.items():
        menu_item = MenuItem.objects.get(id=item_id)
        subtotal = menu_item.price * Decimal(str(quantity))
        total += subtotal
        items.append({
            'menu_item': menu_item,
            'quantity': quantity,
            'subtotal': subtotal
        })
    
    context = {
        'cart_items': items,
        'total': total,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'restaurant/checkout.html', context)

@login_required
def create_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    cart_items = request.session.get('cart', {})
    if not cart_items:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # Create order
    total = Decimal('0.00')
    for item_id, quantity in cart_items.items():
        menu_item = MenuItem.objects.get(id=item_id)
        total += menu_item.price * Decimal(str(quantity))
    
    order = Order.objects.create(
        user=request.user,
        total_amount=total,
        status='pending'
    )
    
    # Create order items
    for item_id, quantity in cart_items.items():
        menu_item = MenuItem.objects.get(id=item_id)
        OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=quantity,
            price_at_time_of_order=menu_item.price
        )
    
    # Create payment intent
    payment_data = create_payment_intent(order)
    if 'error' in payment_data:
        order.delete()
        return JsonResponse({'error': payment_data['error']}, status=400)
    
    return JsonResponse(payment_data)

@csrf_exempt
def stripe_webhook(request):
    return handle_webhook(request)
