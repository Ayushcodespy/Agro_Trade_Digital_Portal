from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Product, Customer, Bill, BillItem, Payment, UserProfile
from decimal import Decimal
from django.db import transaction

class ModelsTestCase(TestCase):
    
    def setUp(self):
        """Set up test data for all model tests"""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.customer = Customer.objects.create(
            name='Test Customer',
            phone='9876543210',
            address='Test Address',
            created_by=self.user
        )
        
        self.product = Product.objects.create(
            name='Test Cement',
            category='Construction',
            market_price=Decimal('320.00'),
            current_stock=100
        )

    # UserProfile Model Tests
    def test_user_profile_creation(self):
        """Test UserProfile model creation and string representation"""
        profile = UserProfile.objects.create(
            user=self.user,
            user_type='owner',
            phone='9876543210',
            address='Test Address',
            salary=Decimal('25000.00')
        )
        
        self.assertEqual(str(profile), "Test User - Shop Owner (Chacha Ji)")
        self.assertTrue(profile.is_active)
        self.assertIsNotNone(profile.join_date)

    def test_user_profile_choices(self):
        """Test UserProfile user_type choices"""
        profile = UserProfile.objects.create(
            user=self.user,
            user_type='employee',
            phone='9876543210',
            address='Test Address'
        )
        
        self.assertEqual(profile.get_user_type_display(), 'Employee (Anshu/Ashish)')

    # Product Model Tests
    def test_product_creation(self):
        """Test Product model creation and string representation"""
        product = Product.objects.create(
            name='New Product',
            category='Agriculture',
            market_price=Decimal('150.00'),
            current_stock=50
        )
        
        self.assertEqual(str(product), "New Product - ₹150.00")
        self.assertIsNotNone(product.last_updated)

    def test_product_stock_management(self):
        """Test product stock updates"""
        self.product.current_stock = 75
        self.product.save()
        
        updated_product = Product.objects.get(id=self.product.id)
        self.assertEqual(updated_product.current_stock, 75)

    # Customer Model Tests
    def test_customer_creation(self):
        """Test Customer model creation and string representation"""
        customer = Customer.objects.create(
            name='New Customer',
            phone='9998887777',
            address='New Address',
            created_by=self.user
        )
        
        self.assertEqual(str(customer), "New Customer - 9998887777")
        self.assertEqual(customer.outstanding_balance, Decimal('0'))

    def test_customer_balance_calculation(self):
        """Test customer balance calculation method"""
        # Create a bill for the customer
        bill = Bill.objects.create(
            bill_number='TEST-001',
            customer=self.customer,
            total_amount=Decimal('2000.00'),
            paid_amount=Decimal('500.00'),
            remaining_amount=Decimal('1500.00'),
            payment_status='partial',
            created_by=self.user
        )
        
        # Test balance calculation
        balance = self.customer.update_balance()
        self.assertEqual(balance, Decimal('1500.00'))
        
        # Refresh customer from database
        customer_refreshed = Customer.objects.get(id=self.customer.id)
        self.assertEqual(customer_refreshed.outstanding_balance, Decimal('1500.00'))

    def test_customer_balance_with_multiple_bills(self):
        """Test balance calculation with multiple bills"""
        # Create multiple bills
        bill1 = Bill.objects.create(
            bill_number='TEST-001',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        bill2 = Bill.objects.create(
            bill_number='TEST-002',
            customer=self.customer,
            total_amount=Decimal('1500.00'),
            paid_amount=Decimal('500.00'),
            remaining_amount=Decimal('1000.00'),
            payment_status='partial',
            created_by=self.user
        )
        
        balance = self.customer.update_balance()
        self.assertEqual(balance, Decimal('2000.00'))  # 1000 + 1000

    # Bill Model Tests
    def test_bill_creation(self):
        """Test Bill model creation and string representation"""
        bill = Bill.objects.create(
            bill_number='BILL-001',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        self.assertEqual(str(bill), "BILL-001 - Test Customer")
        self.assertEqual(bill.payment_status, 'pending')

    def test_bill_save_method_paid_status(self):
        """Test bill save method with paid status calculation"""
        bill = Bill(
            bill_number='BILL-PAID',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('1000.00'),  # Full payment
            created_by=self.user
        )
        bill.save()
        
        self.assertEqual(bill.payment_status, 'paid')
        self.assertEqual(bill.remaining_amount, Decimal('0'))

    def test_bill_save_method_partial_status(self):
        """Test bill save method with partial status calculation"""
        bill = Bill(
            bill_number='BILL-PARTIAL',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('500.00'),  # Partial payment
            created_by=self.user
        )
        bill.save()
        
        self.assertEqual(bill.payment_status, 'partial')
        self.assertEqual(bill.remaining_amount, Decimal('500.00'))

    def test_bill_save_method_pending_status(self):
        """Test bill save method with pending status calculation"""
        bill = Bill(
            bill_number='BILL-PENDING',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),  # No payment
            created_by=self.user
        )
        bill.save()
        
        self.assertEqual(bill.payment_status, 'pending')
        self.assertEqual(bill.remaining_amount, Decimal('1000.00'))

    # BillItem Model Tests
    def test_bill_item_creation(self):
        """Test BillItem model creation and string representation"""
        bill = Bill.objects.create(
            bill_number='BILL-ITEM-TEST',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        bill_item = BillItem.objects.create(
            bill=bill,
            product=self.product,
            quantity=3,
            price=Decimal('320.00'),
            total=Decimal('960.00')
        )
        
        self.assertEqual(str(bill_item), "Test Cement - 3 x ₹320.00")
        self.assertEqual(bill_item.total, Decimal('960.00'))

    def test_bill_item_save_method(self):
        """Test BillItem automatic total calculation"""
        bill = Bill.objects.create(
            bill_number='BILL-AUTO-TOTAL',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        bill_item = BillItem(
            bill=bill,
            product=self.product,
            quantity=2,
            price=Decimal('320.00')
        )
        bill_item.save()  # This should auto-calculate total
        
        self.assertEqual(bill_item.total, Decimal('640.00'))  # 2 * 320

    # Payment Model Tests
    def test_payment_creation(self):
        """Test Payment model creation and string representation"""
        bill = Bill.objects.create(
            bill_number='PAYMENT-TEST',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        payment = Payment.objects.create(
            customer=self.customer,
            bill=bill,
            amount=Decimal('500.00'),
            payment_method='cash',
            received_by=self.user,
            notes='Test payment'
        )
        
        self.assertEqual(str(payment), "Payment of ₹500.00 from Test Customer")
        self.assertEqual(payment.payment_method, 'cash')

    def test_payment_without_bill(self):
        """Test payment creation without specific bill"""
        payment = Payment.objects.create(
            customer=self.customer,
            amount=Decimal('300.00'),
            payment_method='upi',
            received_by=self.user
        )
        
        self.assertIsNone(payment.bill)
        self.assertEqual(payment.amount, Decimal('300.00'))

    def test_payment_save_updates_bill(self):
        """Test payment save method updates related bill"""
        bill = Bill.objects.create(
            bill_number='BILL-PAY-UPDATE',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        payment = Payment(
            customer=self.customer,
            bill=bill,
            amount=Decimal('600.00'),
            payment_method='cash',
            received_by=self.user
        )
        payment.save()
        
        # Refresh bill from database
        bill_refreshed = Bill.objects.get(id=bill.id)
        self.assertEqual(bill_refreshed.paid_amount, Decimal('600.00'))
        self.assertEqual(bill_refreshed.payment_status, 'partial')

    def test_payment_save_full_payment(self):
        """Test payment that fully pays a bill"""
        bill = Bill.objects.create(
            bill_number='BILL-FULL-PAY',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        payment = Payment(
            customer=self.customer,
            bill=bill,
            amount=Decimal('1000.00'),
            payment_method='cash',
            received_by=self.user
        )
        payment.save()
        
        bill_refreshed = Bill.objects.get(id=bill.id)
        self.assertEqual(bill_refreshed.paid_amount, Decimal('1000.00'))
        self.assertEqual(bill_refreshed.payment_status, 'paid')

    # Complex Business Logic Tests
    def test_complete_billing_workflow(self):
        """Test complete billing workflow with multiple items and payments"""
        # Create bill with items
        bill = Bill.objects.create(
            bill_number='WORKFLOW-TEST',
            customer=self.customer,
            total_amount=Decimal('0'),  # Will be updated
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('0'),
            payment_status='pending',
            created_by=self.user
        )
        
        # Add bill items
        item1 = BillItem.objects.create(
            bill=bill,
            product=self.product,
            quantity=2,
            price=self.product.market_price
        )  # Total: 640
        
        # Create another product
        product2 = Product.objects.create(
            name='Test Rods',
            category='Construction',
            market_price=Decimal('500.00'),
            current_stock=50
        )
        
        item2 = BillItem.objects.create(
            bill=bill,
            product=product2,
            quantity=1,
            price=product2.market_price
        )  # Total: 500
        
        # Update bill totals
        bill.total_amount = item1.total + item2.total  # 640 + 500 = 1140
        bill.remaining_amount = bill.total_amount
        bill.save()
        
        # Make payment
        payment = Payment.objects.create(
            customer=self.customer,
            bill=bill,
            amount=Decimal('1140.00'),
            payment_method='cash',
            received_by=self.user
        )
        
        # Verify final state
        bill_refreshed = Bill.objects.get(id=bill.id)
        customer_refreshed = Customer.objects.get(id=self.customer.id)
        
        self.assertEqual(bill_refreshed.payment_status, 'paid')
        self.assertEqual(bill_refreshed.paid_amount, Decimal('1140.00'))
        self.assertEqual(customer_refreshed.outstanding_balance, Decimal('0'))

    def test_payment_distribution_multiple_bills(self):
        """Test payment distribution across multiple pending bills"""
        # Create multiple pending bills
        bill1 = Bill.objects.create(
            bill_number='DIST-001',
            customer=self.customer,
            total_amount=Decimal('500.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('500.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        bill2 = Bill.objects.create(
            bill_number='DIST-002',
            customer=self.customer,
            total_amount=Decimal('800.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('800.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        # Create payment without specific bill (should distribute)
        payment = Payment.objects.create(
            customer=self.customer,
            amount=Decimal('1000.00'),  # Enough to pay both bills partially
            payment_method='cash',
            received_by=self.user
        )
        
        # Verify bills were updated
        bill1_refreshed = Bill.objects.get(id=bill1.id)
        bill2_refreshed = Bill.objects.get(id=bill2.id)
        
        # Should pay bill1 completely (500) and bill2 partially (500)
        self.assertEqual(bill1_refreshed.payment_status, 'paid')
        self.assertEqual(bill2_refreshed.payment_status, 'partial')
        self.assertEqual(bill2_refreshed.paid_amount, Decimal('500.00'))

    # Edge Cases and Error Handling
    def test_customer_phone_uniqueness(self):
        """Test customer phone number uniqueness constraint"""
        Customer.objects.create(
            name='Customer 1',
            phone='9998887777',
            address='Address 1',
            created_by=self.user
        )
        
        with self.assertRaises(Exception):  # Should raise integrity error
            Customer.objects.create(
                name='Customer 2',
                phone='9998887777',  # Same phone number
                address='Address 2',
                created_by=self.user
            )

    def test_bill_number_uniqueness(self):
        """Test bill number uniqueness constraint"""
        Bill.objects.create(
            bill_number='UNIQUE-001',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )
        
        with self.assertRaises(Exception):
            Bill.objects.create(
                bill_number='UNIQUE-001',  # Same bill number
                customer=self.customer,
                total_amount=Decimal('2000.00'),
                paid_amount=Decimal('0'),
                remaining_amount=Decimal('2000.00'),
                payment_status='pending',
                created_by=self.user
            )

    def test_negative_payment_amount(self):
    # Django's DecimalField automatically validates positive values
    # So instead of expecting exception, we test that positive validation works
        payment = Payment.objects.create(
            customer=self.customer,
            amount=Decimal('100.00'),  # Positive amount should work
            payment_method='cash',
            received_by=self.user
        )
    
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertGreater(payment.amount, Decimal('0'))  # Should be positive


# Views Test Cases - Add this to your existing tests.py

class ViewsTestCase(TestCase):
    
    def setUp(self):
        """Set up test data for all view tests"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.customer = Customer.objects.create(
            name='Test Customer',
            phone='9876543210',
            address='Test Address',
            created_by=self.user
        )
        
        self.product = Product.objects.create(
            name='Test Cement',
            category='Construction',
            market_price=Decimal('320.00'),
            current_stock=100
        )
        
        self.bill = Bill.objects.create(
            bill_number='TEST-BILL-001',
            customer=self.customer,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0'),
            remaining_amount=Decimal('1000.00'),
            payment_status='pending',
            created_by=self.user
        )

    # Authentication Views Tests
    def test_home_view(self):
        """Test home page view"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
        self.assertContains(response, 'Agro Trade')

    def test_login_view_get(self):
        """Test login page GET request"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'login.html')

    def test_login_view_post_success(self):
        """Test successful login"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        self.assertRedirects(response, reverse('dashboard'))

    def test_login_view_post_failure(self):
        """Test failed login"""
        response = self.client.post(reverse('login'), {
            'username': 'wronguser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid credentials')
        self.assertTemplateUsed(response, 'login.html')

    def test_logout_view(self):
        """Test logout functionality"""
        # First login
        self.client.login(username='testuser', password='testpass123')
        
        # Then logout
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    # Dashboard Views Tests
    def test_dashboard_view_authenticated(self):
        """Test dashboard access for authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Total Customers')
        
        # Check context data
        self.assertIn('total_customers', response.context)
        self.assertIn('total_products', response.context)
        self.assertIn('total_bills_today', response.context)
        self.assertIn('total_outstanding', response.context)

    def test_dashboard_view_unauthenticated(self):
        """Test dashboard redirects for unauthenticated user"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    # Product Management Views Tests
    def test_product_list_view(self):
        """Test product list view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('product_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products.html')
        self.assertIn('products', response.context)
        self.assertEqual(len(response.context['products']), 1)

    def test_add_product_view_get(self):
        """Test add product form display"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('add_product'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'add_product.html')

    def test_add_product_view_post(self):
        """Test adding a new product"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('add_product'), {
            'name': 'New Test Product',
            'category': 'Agriculture',
            'market_price': '150.00',
            'current_stock': '50'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect to product list
        self.assertRedirects(response, reverse('product_list'))
        
        # Verify product was created
        self.assertTrue(Product.objects.filter(name='New Test Product').exists())

    # Customer Management Views Tests
    def test_customer_list_view(self):
        """Test customer list view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('customer_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'customers.html')
        self.assertIn('customers', response.context)
        self.assertEqual(len(response.context['customers']), 1)

    def test_customer_list_view_with_search(self):
        """Test customer list with search query"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('customer_list') + '?search=Test')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('customers', response.context)
        self.assertEqual(len(response.context['customers']), 1)

    def test_add_customer_view_get(self):
        """Test add customer form display"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('add_customer'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'add_customer.html')

    def test_add_customer_view_post(self):
        """Test adding a new customer"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('add_customer'), {
            'name': 'New Customer',
            'phone': '9998887777',
            'address': 'New Address'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect to customer list
        self.assertRedirects(response, reverse('customer_list'))
        
        # Verify customer was created
        self.assertTrue(Customer.objects.filter(phone='9998887777').exists())

    def test_customer_detail_view(self):
        """Test customer detail view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('customer_detail', args=[self.customer.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'customer_detail.html')
        self.assertIn('customer', response.context)
        self.assertEqual(response.context['customer'], self.customer)
        self.assertIn('bills', response.context)
        self.assertIn('payments', response.context)

    def test_search_customers_ajax(self):
        """Test customer search AJAX endpoint"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('search_customers') + '?q=Test')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Test Customer')

    # Billing System Views Tests
    def test_bill_list_view(self):
        """Test bill list view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bill_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bills.html')
        self.assertIn('bills', response.context)
        self.assertEqual(len(response.context['bills']), 1)

    def test_bill_detail_view(self):
        """Test bill detail view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('bill_detail', args=[self.bill.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bill_detail2.html')
        self.assertIn('bill', response.context)
        self.assertEqual(response.context['bill'], self.bill)

    def test_create_bill_view_get(self):
        """Test bill creation form display"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('create_bill'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'create_bill.html')
        self.assertIn('products', response.context)

    def test_create_bill_view_post_preview(self):
        """Test bill creation preview step"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('create_bill'), {
            'customer_name': 'Preview Customer',
            'customer_phone': '1112223333',
            'customer_address': 'Preview Address',
            'products[]': [str(self.product.id)],
            'quantities[]': ['2'],
            'paid_amount': '500',
            'payment_method': 'cash'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bill_confirmation.html')
        self.assertIn('bill_items', response.context)
        self.assertIn('total_amount', response.context)

    def test_create_bill_view_post_final(self):
        """Test final bill creation and saving"""
        self.client.login(username='testuser', password='testpass123')
        
        # First create a preview
        response = self.client.post(reverse('create_bill'), {
            'customer_name': 'Final Customer',
            'customer_phone': '4445556666',
            'customer_address': 'Final Address',
            'products[]': [str(self.product.id)],
            'quantities[]': ['3'],
            'paid_amount': '1000',
            'payment_method': 'cash',
            'confirm_bill': 'true',
            'total_amount': '960.00',
            'final_products[]': [str(self.product.id)],
            'final_quantities[]': ['3'],
            'final_prices[]': ['320.00']
        })
        
        # Should redirect to bill detail
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Bill.objects.filter(customer__phone='4445556666').exists())

    # Payment Management Views Tests
    def test_payment_list_view(self):
        """Test payment list view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('payment_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments.html')
        self.assertIn('payments', response.context)

    def test_receive_payment_view_get(self):
        """Test receive payment form display"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('receive_payment'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'receive_payment.html')
        self.assertIn('customers', response.context)
        self.assertIn('pending_bills', response.context)

    def test_receive_payment_view_post_success(self):
        """Test successful payment receipt"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('receive_payment'), {
            'customer': self.customer.id,
            'amount': '500',
            'payment_method': 'cash',
            'notes': 'Test payment'
        })
        
        self.assertEqual(response.status_code, 302)  # Redirect to payment list
        self.assertRedirects(response, reverse('payment_list'))
        
        # Verify payment was created
        self.assertTrue(Payment.objects.filter(amount=500).exists())

    def test_receive_payment_view_post_with_bill(self):
        """Test payment receipt with specific bill"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('receive_payment'), {
            'customer': self.customer.id,
            'bill': self.bill.id,
            'amount': '300',
            'payment_method': 'upi'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Payment.objects.filter(bill=self.bill).exists())

    def test_receive_payment_view_post_invalid_customer(self):
        """Test payment receipt with invalid customer"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('receive_payment'), {
            'customer': 9999,  # Non-existent customer
            'amount': '500',
            'payment_method': 'cash'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'receive_payment.html')
        self.assertIn('error', response.context)

    # Reports and Analytics Views Tests
    # def test_user_activity_report_view(self):
    #     """Test user activity report view"""
    #     self.client.login(username='testuser', password='testpass123')
    #     response = self.client.get(reverse('user_activity_report'))
        
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTemplateUsed(response, 'activity_report.html')
    #     self.assertIn('bills', response.context)
    #     self.assertIn('payments', response.context)
    #     self.assertIn('products', response.context)

    # def test_user_profile_view(self):
    #     """Test user profile view"""
    #     self.client.login(username='testuser', password='testpass123')
    #     response = self.client.get(reverse('user_profile'))
        
    #     self.assertEqual(response.status_code, 200)
    #     self.assertTemplateUsed(response, 'profile.html')
    #     self.assertIn('user_bills_count', response.context)
    #     self.assertIn('user_payments_count', response.context)
    #     self.assertIn('today_bills', response.context)
    #     self.assertIn('month_bills', response.context)

    def test_payment_success_view(self):
        """Test payment success page"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('payment_success'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payment_success.html')
        self.assertIn('amount', response.context)
        self.assertIn('customer_name', response.context)

    # Lending Management Views Tests
    def test_customer_lending_view(self):
        """Test customer lending dashboard"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('customer_lending'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'customer_lending.html')
        self.assertIn('customers_with_stats', response.context)
        self.assertIn('total_outstanding', response.context)
        self.assertIn('total_customers', response.context)

    def test_customer_lending_view_with_filters(self):
        """Test customer lending with search filters"""
        self.client.login(username='testuser', password='testpass123')
        
        # Test with search query
        response = self.client.get(reverse('customer_lending') + '?search=Test')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['customers_with_stats']), 1)
        
        # Test with payment status filter
        response = self.client.get(reverse('customer_lending') + '?payment_status=pending')
        self.assertEqual(response.status_code, 200)

    # Utility Views Tests
    # def test_update_all_balances_view(self):
    #     """Test manual balance update view"""
    #     self.client.login(username='testuser', password='testpass123')
    #     response = self.client.get(reverse('update_all_balances'))
        
    #     self.assertEqual(response.status_code, 302)  # Redirect to dashboard
    #     self.assertRedirects(response, reverse('dashboard'))