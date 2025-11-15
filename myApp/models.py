from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

class UserProfile(models.Model):
    USER_TYPES = (
        ('owner', 'Shop Owner (Chacha Ji)'),
        ('employee', 'Employee (Anshu/Ashish)'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    join_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.get_user_type_display()}"

class Product(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    market_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_stock = models.PositiveIntegerField(default=0)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ₹{self.market_price}"

class Customer(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField()
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.name} - {self.phone}"

    def update_balance(self):
        """Calculate outstanding balance from all pending/partial bills"""
        total_outstanding = Bill.objects.filter(
            customer=self, 
            payment_status__in=['pending', 'partial']
        ).aggregate(total=Sum('remaining_amount'))['total'] or Decimal('0')
        
        self.outstanding_balance = total_outstanding
        self.save()
        return self.outstanding_balance

class Bill(models.Model):
    bill_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=[
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('pending', 'Pending')
    ], default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        # Calculate remaining amount
        self.remaining_amount = self.total_amount - self.paid_amount
        
        # Update payment status
        if self.paid_amount == 0:
            self.payment_status = 'pending'
        elif self.paid_amount >= self.total_amount:
            self.payment_status = 'paid'
            self.remaining_amount = Decimal('0')
        else:
            self.payment_status = 'partial'
        
        super().save(*args, **kwargs)
        
        # Update customer balance
        self.customer.update_balance()

    def __str__(self):
        return f"{self.bill_number} - {self.customer.name}"

class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} x ₹{self.price}"

class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank', 'Bank Transfer')
    ])
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Update related bill if specified
        if self.bill:
            # Re-fetch the bill to get current paid_amount
            bill = Bill.objects.get(id=self.bill.id)
            bill.paid_amount += self.amount
            
            # Ensure paid_amount doesn't exceed total_amount
            if bill.paid_amount > bill.total_amount:
                bill.paid_amount = bill.total_amount
            
            bill.save()
        
        # Update customer balance
        self.customer.update_balance()

    def delete(self, *args, **kwargs):
        customer = self.customer
        bill = self.bill
        
        super().delete(*args, **kwargs)
        
        # Update bill if exists
        if bill:
            # Re-fetch the bill to get current paid_amount
            bill_refreshed = Bill.objects.get(id=bill.id)
            bill_refreshed.paid_amount -= self.amount
            
            # Ensure paid_amount doesn't go below 0
            if bill_refreshed.paid_amount < 0:
                bill_refreshed.paid_amount = Decimal('0')
            
            bill_refreshed.save()
        
        # Update customer balance
        customer.update_balance()

    def __str__(self):
        return f"Payment of ₹{self.amount} from {self.customer.name}"

# Signals to handle balance updates automatically
@receiver(post_save, sender=Bill)
def update_customer_balance_on_bill_save(sender, instance, **kwargs):
    """Update customer balance when bill is saved"""
    instance.customer.update_balance()

@receiver(post_delete, sender=Bill)
def update_customer_balance_on_bill_delete(sender, instance, **kwargs):
    """Update customer balance when bill is deleted"""
    instance.customer.update_balance()

@receiver(post_save, sender=Payment)
def update_customer_balance_on_payment_save(sender, instance, **kwargs):
    """Update customer balance when payment is saved"""
    instance.customer.update_balance()

@receiver(post_delete, sender=Payment)
def update_customer_balance_on_payment_delete(sender, instance, **kwargs):
    """Update customer balance when payment is deleted"""
    instance.customer.update_balance()