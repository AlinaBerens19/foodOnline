from datetime import datetime
import json
from decimal import *
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from marketplace.context_processors import get_cart_amount
from marketplace.models import Cart, Tax
from menu.models import FoodItem
from orders.forms import OrderForm
from orders.models import Order, Payment, OrderedFood
from orders.utils import generate_order_number
from django.contrib.auth.decorators import login_required
from accounts.utils import send_notification
from vendor.models import Vendor
from django.contrib.sites.shortcuts import get_current_site
from .utils import order_total_by_vendor

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        # 👇️ if passed in object is instance of Decimal
        # convert it to a string
        if isinstance(obj, Decimal):
            return str(obj)
        # 👇️ otherwise use the default behavior
        return json.JSONEncoder.default(self, obj)


# Create your views here.
@login_required(login_url='login')
def place_order(request):
    cart_items = Cart.objects.filter(user=request.user).order_by('created_at')
    cart_counts = cart_items.count()

    if cart_counts <= 0:
        return redirect('marketplace')

    vendor_ids = []
    for i in cart_items:
        if i.fooditem.vendor.id not in vendor_ids:
            vendor_ids.append(i.fooditem.vendor.id)  

    # The Json Model for saving tax info about Order per each Vendor
    # {"vendor_id": {"subtotal": {"tax_type": {"tax_percentage": "tax_amount"}}}}        
    get_tax = Tax.objects.filter(is_active=True)
    subtotal = 0
    total_data = {}
    k = {}

    for i in cart_items:
        fooditem = FoodItem.objects.get(pk=i.fooditem.id, vendor_id__in=vendor_ids)
        v_id = fooditem.vendor.id
        if v_id in k:
            subtotal += (fooditem.price * i.quantity)
            k[v_id] = subtotal
        else:
            subtotal = (fooditem.price * i.quantity)
            k[v_id] = subtotal
            print("Vendor ID: ", v_id, " - Vendor name: ", Vendor.objects.get(pk=v_id))
        
        print("Subtotal: ", k)    

        # Update tax information
        tax_dict = {}
        for i in get_tax:
            tax_amount = round((i.tax_percentage * subtotal)/100, 2)
            tax_dict.update({i.tax_type: {str(i.tax_percentage): str(tax_amount)}})    

        # Construct total data
        total_data.update({fooditem.vendor.id: {str(subtotal): str(tax_dict)}})
        print("TOTAL DATA==> ", total_data)

    subtotal = get_cart_amount(request)['subtotal']
    total_tax = get_cart_amount(request)['tax']
    grand_total = get_cart_amount(request)['grand_total']
    tax_data = get_cart_amount(request)['tax_dict']

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = Order()
            order.first_name = form.cleaned_data['first_name']
            order.last_name = form.cleaned_data['last_name']
            order.phone = form.cleaned_data['phone']
            order.email = form.cleaned_data['email']
            order.address = form.cleaned_data['address']
            order.country = form.cleaned_data['country']
            order.state = form.cleaned_data['state']
            order.city = form.cleaned_data['city']
            order.pin_code = form.cleaned_data['pin_code']
            order.user = request.user
            order.total = grand_total
            order.total_data = json.dumps(total_data)
            order.tax_data = json.dumps(tax_data, cls=DecimalEncoder)
            order.total_tax = total_tax
            order.payment_method = request.POST['payment_method']
            order.save() # order id/ pk is generated
            order.order_number = generate_order_number(order.id)
            order.vendors.add(*vendor_ids)
            order.save()

            print('ORDER TOTAL FROM ORDER==> ', order.total)
            print('ORDER TOTAL TAX FROM ORDER==> ', order.total_tax)

            context = {
                'cart_items': cart_items,
                'order': order,
            }
            return render(request, 'orders/place_order.html', context)

        else:
            print('Form IS NOT VALID')
            print(form.errors)    
    else:
        print(request.method)

    return render(request, 'orders/place_order.html')


@login_required(login_url='login')
def payments(request):

    # Check if the request ajax or not
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == 'POST':
        # STORE THE PAYMENT DETAILS IN THE PAYMENT MODEL
        order_number = request.POST.get('order_number')
        transaction_id = request.POST.get('transaction_id')
        payment_method = request.POST.get('payment_method')
        status = request.POST.get('status')
        grand_total = request.POST.get('grand_total')
        total_tax = request.POST.get('total_tax')

        order = Order.objects.get(user=request.user, order_number=order_number)
        print('ORDER TOTAL ==>', order.order_number)
        print('ORDER ==>', order)

        payment = Payment(
            user = request.user,
            transaction_id = transaction_id,
            payment_method = payment_method,
            amount = grand_total,
            status = status,
        )

        payment.save()

        # UPDATE THE ORDER MODEL
        order.payment = payment
        order.is_ordered = True
        order.save()

        # MOVE THE CART ITEMS TO THE FOOD ORDERED MODEL
        cart_items = Cart.objects.filter(user=request.user)
        for item in cart_items:
            ordered_food = OrderedFood()
            ordered_food.order = order
            ordered_food.payment = payment
            ordered_food.user = request.user
            ordered_food.fooditem = item.fooditem
            ordered_food.quantity = item.quantity
            ordered_food.price = item.fooditem.price
            ordered_food.amount = item.fooditem.price * item.quantity
            ordered_food.save()

        # SEND ORDER CONFIRMATION EMAIL TO CUSTOMER
        mail_subject = 'Thank you for ordering with us'
        mail_template = 'orders/order_confirmation_email.html'
        
        orderedfood = OrderedFood.objects.filter(order=order)
        customer_subtotal = 0
        for i in orderedfood:
            customer_subtotal += (i.price * i.quantity)
        tax_data = json.loads(order.tax_data)    

        context = {
            'user': request.user,
            'order': order,
            'to_email': order.email,
            'orderedfood': orderedfood,
            'domain': get_current_site(request),
            'customer_subtotal': customer_subtotal,
            'tax_data': tax_data,
        }

        try:
            send_notification(mail_subject, mail_template, context)
        except Exception as e:
            print(e)


        # SEND ORDER RECEIVED EMAIL TO VENDOR
        mail_subject = 'You have received new order'
        mail_template = 'orders/new_order_received.html'
        to_emails = []

        for i in cart_items:
            if i.fooditem.vendor.user.email not in to_emails:
                to_emails.append(i.fooditem.vendor.user.email)    

                ordered_food_for_vendor = OrderedFood.objects.filter(order=order, fooditem__vendor=i.fooditem.vendor)
                print('ORDERED FOOD FOR VENDOR ==> ', ordered_food_for_vendor)

                context = {
                    'user': request.user,
                    'order': order,
                    'to_email': to_emails,
                    'ordered_food_for_vendor': ordered_food_for_vendor,
                    'vendor_subtotal': order_total_by_vendor(order, i.fooditem.vendor.id)['subtotal'],
                    'tax_data': order_total_by_vendor(order, i.fooditem.vendor.id)['tax_dict'],
                    'vendor_grand_total': order_total_by_vendor(order, i.fooditem.vendor.id)['grand_total'],
                }

        try:
            send_notification(mail_subject, mail_template, context)
        except Exception as e:
            print(e)

        # CLEAR THE CART IF THE PAYMENT IS SUCCESS
        cart_items.delete()

        # RETURN BACK TO AJAX IF THE PAYMENT IS SUCCESSFUL
        response = {
            'order_number': order_number,
            'transaction_id': transaction_id,
        }

        return JsonResponse(response) 

    return HttpResponse('Payment')


def order_complete(request):
    order_number = request.GET.get('order_no')
    transaction_id = request.GET.get('trans_id')

    try:
        order = Order.objects.get(order_number=order_number, payment__transaction_id=transaction_id, is_ordered=True)
        ordered_food = OrderedFood.objects.filter(order=order)

        subtotal = 0
        for item in ordered_food:
            subtotal += (item.price * item.quantity)

        tax_data = json.loads(order.tax_data)

        context = {
            'order': order,
            'ordered_food': ordered_food,
            'subtotal': subtotal,
            'tax_data': tax_data, 
        }

        return render(request, 'orders/order_complete.html', context)
    except Exception as e:
        print('Exception ==> ', e)
        return redirect('home')    


    

