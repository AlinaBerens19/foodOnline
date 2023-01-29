
import json
from decimal import *
from django.shortcuts import redirect, render
from marketplace.context_processors import get_cart_amount
from django.contrib import messages
from marketplace.models import Cart
from orders.forms import OrderForm
from orders.models import Order
from orders.utils import generate_order_number


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        # 👇️ if passed in object is instance of Decimal
        # convert it to a string
        if isinstance(obj, Decimal):
            return str(obj)
        # 👇️ otherwise use the default behavior
        return json.JSONEncoder.default(self, obj)


# Create your views here.
def place_order(request):
    cart_items = Cart.objects.filter(user=request.user).order_by('created_at')
    cart_counts = cart_items.count()

    if cart_counts <= 0:
        return redirect('marketplace')

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
            order.tax_data = json.dumps(tax_data, cls=DecimalEncoder)
            order.total_tax = total_tax
            order.payment_method = request.POST['payment_method']
            order.save() # order id/ pk is generated
            order.order_number = generate_order_number(order.id)
            order.save()
            return redirect('place_order')

        else:
            print('Form IS NOT VALID')
            print(form.errors)    
    else:
        print(request.method)

    return render(request, 'orders/place_order.html')


