from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate, logout
from django.utils import timezone
from decimal import Decimal, InvalidOperation 
from .models import Product, Customer, Bill, BillItem, Payment, UserProfile
from django.http import JsonResponse
from django.db.models import Q, Sum 
import json


# Home Page - Public
def home(request):
    return render(request, 'home.html')

# Dashboard - Login Required
@login_required
def dashboard(request):
    total_products = Product.objects.count()
    total_customers = Customer.objects.count()
    total_bills_today = Bill.objects.filter(date__date=timezone.now().date()).count()
    
    # Calculate total outstanding balance - FIXED
    total_outstanding_result = Customer.objects.aggregate(
        total=Sum('outstanding_balance')
    )['total'] or Decimal('0')
    
    print(f"DASHBOARD: Total Outstanding: {total_outstanding_result}")
    
    context = {
        'total_products': total_products,
        'total_customers': total_customers,
        'total_bills_today': total_bills_today,
        'total_outstanding': total_outstanding_result,
        'current_user': request.user
    }
    return render(request, 'dashboard.html', context)



# Product Management
@login_required
def product_list(request):
    products = Product.objects.all()
    return render(request, 'products.html', {'products': products})



@login_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        market_price = request.POST.get('market_price')
        current_stock = request.POST.get('current_stock')
        
        Product.objects.create(
            name=name,
            category=category,
            market_price=market_price,
            current_stock=current_stock
        )
        return redirect('product_list')
    
    return render(request, 'add_product.html')


# Customer Management
@login_required
def customer_list(request):
    search_query = request.GET.get('search', '')
    
    if search_query:
        customers = Customer.objects.filter(
            Q(name__icontains=search_query) | 
            Q(phone__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    else:
        customers = Customer.objects.all()
    
    return render(request, 'customers.html', {'customers': customers})

@login_required
def add_customer(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        Customer.objects.create(
            name=name,
            phone=phone,
            address=address,
            created_by=request.user
        )
        return redirect('customer_list')
    
    return render(request, 'add_customer.html')


# Customer Search for AJAX
@login_required
def search_customers(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.filter(
        Q(name__icontains=query) | 
        Q(phone__icontains=query) |
        Q(address__icontains=query)
    )[:10]
    
    results = []
    for customer in customers:
        results.append({
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'address': customer.address,
            'display_text': f"{customer.name} - {customer.phone} - {customer.address}"
        })
    
    return JsonResponse(results, safe=False)


@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Get all bills for this customer
    bills = Bill.objects.filter(customer=customer).order_by('-date')
    
    # Get all payments for this customer
    payments = Payment.objects.filter(customer=customer).order_by('-date')
    
    # Calculate statistics
    total_bills = bills.count()
    total_paid = sum(payment.amount for payment in payments)
    total_purchases = sum(bill.total_amount for bill in bills)
    
    context = {
        'customer': customer,
        'bills': bills,
        'payments': payments,
        'total_bills': total_bills,
        'total_paid': total_paid,
        'total_purchases': total_purchases,
        'outstanding_balance': customer.outstanding_balance
    }
    
    return render(request, 'customer_detail.html', context)



# Bill Generation - UPDATED WITH CUSTOMER SEARCH
@login_required
def create_bill(request):
    if request.method == 'POST':
        # Check if it's final confirmation
        if 'confirm_bill' in request.POST:
            return save_final_bill(request)
        
        # Preview step
        customer_name = request.POST.get('customer_name')
        customer_phone = request.POST.get('customer_phone')
        customer_address = request.POST.get('customer_address')
        paid_amount = Decimal(request.POST.get('paid_amount', 0))
        payment_method = request.POST.get('payment_method', 'cash')
        
        # Process products
        products = request.POST.getlist('products[]')
        quantities = request.POST.getlist('quantities[]')
        
        # Calculate bill items
        bill_items = []
        total_amount = Decimal('0')
        
        for i in range(len(products)):
            if products[i] and quantities[i]:
                try:
                    product = Product.objects.get(id=products[i])
                    quantity = int(quantities[i])
                    item_total = product.market_price * quantity
                    
                    bill_items.append({
                        'product': product,
                        'quantity': quantity,
                        'price': product.market_price,
                        'total': item_total
                    })
                    
                    total_amount += item_total
                except (Product.DoesNotExist, ValueError):
                    continue
        
        remaining_amount = total_amount - paid_amount
        payment_status = 'paid' if paid_amount >= total_amount else 'partial' if paid_amount > 0 else 'pending'
        
        context = {
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
            'paid_amount': paid_amount,
            'payment_method': payment_method,
            'bill_items': bill_items,
            'total_amount': total_amount,
            'remaining_amount': remaining_amount,
            'payment_status': payment_status
        }
        
        return render(request, 'bill_confirmation.html', context)
    
    # GET request - show bill creation form
    customer_id = request.GET.get('customer_id')
    initial_customer = None
    if customer_id:
        try:
            initial_customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            pass
    
    products = Product.objects.all()
    return render(request, 'create_bill.html', {
        'products': products,
        'initial_customer': initial_customer
    })

def save_final_bill(request):
    # Save the final bill to database
    customer_name = request.POST.get('customer_name')
    customer_phone = request.POST.get('customer_phone')
    customer_address = request.POST.get('customer_address')
    paid_amount = Decimal(request.POST.get('paid_amount', 0))
    payment_method = request.POST.get('payment_method', 'cash')
    total_amount = Decimal(request.POST.get('total_amount', 0))
    
    # Find or create customer
    customer, created = Customer.objects.get_or_create(
        phone=customer_phone,
        defaults={
            'name': customer_name,
            'address': customer_address,
            'created_by': request.user
        }
    )
    
    if not created:
        customer.name = customer_name
        customer.address = customer_address
        customer.save()
    
    # Pehle bill create karein with ZERO paid amount
    bill = Bill.objects.create(
        bill_number=f"BILL-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
        customer=customer,
        total_amount=total_amount,
        paid_amount=0,  # PEHLE ZERO SET KAREIN
        payment_status='pending',
        created_by=request.user
    )
    
    # Add bill items
    products = request.POST.getlist('final_products[]')
    quantities = request.POST.getlist('final_quantities[]')
    prices = request.POST.getlist('final_prices[]')
    
    for i in range(len(products)):
        if products[i] and quantities[i] and prices[i]:
            try:
                product = Product.objects.get(id=products[i])
                quantity = int(quantities[i])
                price = Decimal(prices[i])
                
                BillItem.objects.create(
                    bill=bill,
                    product=product,
                    quantity=quantity,
                    price=price,
                    total=price * quantity
                )
                
                # Update stock
                product.current_stock -= quantity
                product.save()
            except (Product.DoesNotExist, ValueError):
                continue
    
    # Ab payment create karein (yeh automatically bill update karega)
    if paid_amount > 0:
        Payment.objects.create(
            customer=customer,
            bill=bill,  # Bill link karein
            amount=paid_amount,
            payment_method=payment_method,
            received_by=request.user,
            notes=f"Payment for bill {bill.bill_number}"
        )
    
    return redirect('bill_detail', bill_id=bill.id)


@login_required
def search_customers(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.filter(
        Q(name__icontains=query) | 
        Q(phone__icontains=query) |
        Q(address__icontains=query)
    )[:10]
    
    results = []
    for customer in customers:
        # Get last purchase date
        last_bill = Bill.objects.filter(customer=customer).order_by('-date').first()
        last_purchase = last_bill.date.strftime("%d %b %Y") if last_bill else "Never"
        
        results.append({
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'address': customer.address,
            'outstanding_balance': float(customer.outstanding_balance),
            'last_purchase': last_purchase,
            'display_text': f"{customer.name} - {customer.phone} - {customer.address}"
        })

    
    return JsonResponse(results, safe=False)



@login_required
def bill_detail(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)
    return render(request, 'bill_detail2.html', {'bill': bill})




@login_required
def bill_list(request):
    bills = Bill.objects.all().order_by('-date')
    return render(request, 'bills.html', {'bills': bills})




# Payment Management
@login_required
def receive_payment(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        bill_id = request.POST.get('bill')
        amount = Decimal(request.POST.get('amount', 0))
        payment_method = request.POST.get('payment_method')
        notes = request.POST.get('notes', '')
        
        try:
            customer = Customer.objects.get(id=customer_id)
            bill = None
            if bill_id and bill_id != 'null':
                bill = Bill.objects.get(id=bill_id)
            
            print(f"VIEW: Creating payment - Customer: {customer.name}, Amount: {amount}, Bill: {bill}")
            
            # Create payment
            payment = Payment(
                customer=customer,
                bill=bill,
                amount=amount,
                payment_method=payment_method,
                received_by=request.user,
                notes=notes
            )
            payment.save()
            
            # Force customer balance update
            customer.update_balance()
            
            print(f"SUCCESS: Payment of ₹{amount} received from {customer.name}")
            return redirect('payment_list')
            
        except (Customer.DoesNotExist, Bill.DoesNotExist) as e:
            print(f"ERROR: Invalid customer or bill selected - {e}")
            return render(request, 'receive_payment.html', {
                'customers': Customer.objects.all(),
                'pending_bills': Bill.objects.filter(payment_status__in=['pending', 'partial']),
                'error': 'Invalid customer or bill selected.'
            })
        except Exception as e:
            print(f"ERROR: Payment processing failed - {e}")
            return render(request, 'receive_payment.html', {
                'customers': Customer.objects.all(),
                'pending_bills': Bill.objects.filter(payment_status__in=['pending', 'partial']),
                'error': f'Error processing payment: {str(e)}'
            })
    
    # GET request handling
    customers = Customer.objects.all()
    pending_bills = Bill.objects.filter(payment_status__in=['pending', 'partial'])
    
    return render(request, 'receive_payment.html', {
        'customers': customers,
        'pending_bills': pending_bills
    })


@login_required
def payment_list(request):
    payments = Payment.objects.all().order_by('-date')
    return render(request, 'payments.html', {'payments': payments})




# Reports & Tracking
@login_required
def user_activity_report(request):
    bills = Bill.objects.all().order_by('-date')
    payments = Payment.objects.all().order_by('-date')
    products = Product.objects.all().order_by('-last_updated')
    
    context = {
        'bills': bills,
        'payments': payments,
        'products': products,
    }
    return render(request, 'activity_report.html', context)




# User Profile
@login_required
def user_profile(request):
    # Get user stats
    user_bills_count = Bill.objects.filter(created_by=request.user).count()
    user_payments_count = Payment.objects.filter(received_by=request.user).count()
    
    # Today's bills count
    today_bills = Bill.objects.filter(
        created_by=request.user,
        date__date=timezone.now().date()
    ).count()
    
    # This month's bills count
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_bills = Bill.objects.filter(
        created_by=request.user,
        date__gte=month_start
    ).count()
    
    # Sample recent activities
    recent_activities = [
        {
            'action': 'Bill Created',
            'details': 'BILL-20240918-234512 for Rajesh Kumar',
            'time': timezone.now() - timezone.timedelta(minutes=30)
        },
        {
            'action': 'Payment Received',
            'details': '₹2,500 from Amit Sharma',
            'time': timezone.now() - timezone.timedelta(hours=2)
        },
        {
            'action': 'New Customer Added',
            'details': 'Sunita Devi registered',
            'time': timezone.now() - timezone.timedelta(days=1)
        }
    ]
    
    context = {
        'user_bills_count': user_bills_count,
        'user_payments_count': user_payments_count,
        'today_bills': today_bills,
        'month_bills': month_bills,
        'recent_activities': recent_activities
    }
    
    return render(request, 'profile.html', context)




# Login View
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


# Register View (NEW)
def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Automatically create UserProfile
            UserProfile.objects.create(
                user=user,
                user_type='employee',  # Default as employee
                phone='',  # Empty initially
                address=''  # Empty initially
            )
            
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = UserCreationForm()
    
    return render(request, 'register.html', {'form': form})



# Payment Success Page
@login_required
def payment_success(request):
    # Get the latest payment for display
    latest_payment = Payment.objects.filter(received_by=request.user).last()
    
    context = {
        'amount': latest_payment.amount if latest_payment else Decimal('0'),
        'customer_name': latest_payment.customer.name if latest_payment else '',
        'payment_method': latest_payment.get_payment_method_display() if latest_payment else ''
    }
    
    return render(request, 'payment_success.html', context)



@login_required
def customer_lending(request):
    search_query = request.GET.get('search', '')
    village_filter = request.GET.get('village', '')
    payment_status = request.GET.get('payment_status', '')
    
    customers = Customer.objects.all()
    
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) | 
            Q(phone__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    
    if village_filter:
        customers = customers.filter(address__icontains=village_filter)
    
    if payment_status == 'pending':
        customers = customers.filter(outstanding_balance__gt=0)
    elif payment_status == 'completed':
        customers = customers.filter(outstanding_balance=0)
    elif payment_status == 'high_balance':
        customers = customers.filter(outstanding_balance__gt=5000)
    
    customers_with_stats = []
    total_outstanding = Decimal('0')
    pending_customers_count = 0  # NEW: Count only customers with outstanding balance
    
    for customer in customers:
        customer_bills = Bill.objects.filter(customer=customer)
        total_purchases = sum(bill.total_amount for bill in customer_bills)
        
        #  Count only if outstanding balance > 0
        if customer.outstanding_balance > 0:
            pending_customers_count += 1
        
        customers_with_stats.append({
            'customer': customer,
            'total_bills': customer_bills.count(),
            'total_purchases': total_purchases,
            'outstanding_balance': customer.outstanding_balance
        })
        
        total_outstanding += customer.outstanding_balance
    
    all_customers = Customer.objects.exclude(Q(address__isnull=True) | Q(address=''))
    unique_villages = list(set(customer.address for customer in all_customers))[:20]
    
    context = {
        'customers_with_stats': customers_with_stats,
        'search_query': search_query,
        'village_filter': village_filter,
        'payment_status': payment_status,
        'unique_villages': unique_villages,
        'total_customers': customers.count(),
        'total_outstanding': total_outstanding,
        'pending_customers_count': pending_customers_count,  # ✅ NEW
        'filtered': any([search_query, village_filter, payment_status])
    }
    
    return render(request, 'customer_lending.html', context)


@login_required
def customer_detail(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    
    # Get all bills with items
    bills = Bill.objects.filter(customer=customer).order_by('-date').prefetch_related('items')
    
    # Get all payments
    payments = Payment.objects.filter(customer=customer).order_by('-date')
    
    # Calculate statistics
    total_bills = bills.count()
    total_paid = sum(payment.amount for payment in payments)
    total_purchases = sum(bill.total_amount for bill in bills)
    
    # Payment history timeline
    payment_history = []
    for payment in payments:
        payment_history.append({
            'type': 'payment',
            'date': payment.date,
            'amount': payment.amount,
            'details': f"Payment received - {payment.get_payment_method_display()}"
        })
    
    for bill in bills:
        payment_history.append({
            'type': 'purchase',
            'date': bill.date,
            'amount': bill.total_amount,
            'details': f"Purchase - {bill.bill_number}"
        })
    
    # Sort by date
    payment_history.sort(key=lambda x: x['date'], reverse=True)
    
    context = {
        'customer': customer,
        'bills': bills,
        'payments': payments,
        'payment_history': payment_history[:20],  # Last 20 transactions
        'total_bills': total_bills,
        'total_paid': total_paid,
        'total_purchases': total_purchases,
        'outstanding_balance': customer.outstanding_balance
    }
    
    return render(request, 'customer_detail.html', context)


@login_required
def update_all_balances(request):
    """Manual function to update all customer balances"""
    customers = Customer.objects.all()
    updated_count = 0
    
    for customer in customers:
        old_balance = customer.outstanding_balance
        new_balance = customer.update_balance()
        
        if old_balance != new_balance:
            updated_count += 1
            print(f"Updated {customer.name}: {old_balance} -> {new_balance}")
    
    messages.success(request, f'Updated balances for {updated_count} customers')
    return redirect('dashboard')


@login_required
def employee_list(request):
    """Only owner can view employees"""
    if not request.user.userprofile.user_type == 'owner':
        messages.error(request, 'Only shop owner can access this page.')
        return redirect('dashboard')
    
    employees = UserProfile.objects.filter(created_by=request.user, user_type='employee')
    return render(request, 'employee_list.html', {'employees': employees})

@login_required
def add_employee(request):
    """Only owner can add employees"""
    if not request.user.userprofile.user_type == 'owner':
        messages.error(request, 'Only shop owner can add employees.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            # Create user
            user = form.save()
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()
            
            # Create employee profile
            UserProfile.objects.create(
                user=user,
                user_type='employee',
                phone=request.POST.get('phone', ''),
                address=request.POST.get('address', ''),
                salary=request.POST.get('salary', ''),
                created_by=request.user  # Set the owner who created this employee
            )
            
            messages.success(request, f'Employee {user.username} added successfully!')
            return redirect('employee_list')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserCreationForm()
    
    return render(request, 'add_employee.html', {'form': form})

@login_required
def toggle_employee_status(request, employee_id):
    """Activate/Deactivate employee"""
    if not request.user.userprofile.user_type == 'owner':
        messages.error(request, 'Only shop owner can manage employees.')
        return redirect('dashboard')
    
    try:
        employee_profile = UserProfile.objects.get(id=employee_id, created_by=request.user)
        employee_profile.is_active = not employee_profile.is_active
        employee_profile.save()
        
        status = "activated" if employee_profile.is_active else "deactivated"
        messages.success(request, f'Employee {employee_profile.user.username} {status} successfully!')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Employee not found.')
    
    return redirect('employee_list')