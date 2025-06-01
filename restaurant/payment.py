import stripe
from django.conf import settings
from django.http import JsonResponse
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_payment_intent(order):
    try:
        # Convert order total to cents
        amount = int(order.total_amount * Decimal('100'))
        
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=settings.CURRENCY.lower(),
            metadata={
                'order_id': order.id,
                'customer_email': order.user.email
            }
        )
        return {'client_secret': intent.client_secret}
    except Exception as e:
        return {'error': str(e)}

def handle_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        
        # Update order status
        from .models import Order
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'preparing'
            order.save()
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)

    return JsonResponse({'status': 'success'}) 