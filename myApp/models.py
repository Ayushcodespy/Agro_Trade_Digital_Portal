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
        """Calculate outstanding balance from ALL bills (including paid ones for accuracy)"""
        try:
            # Calculate total outstanding from ALL bills' remaining_amount
            total_outstanding = Bill.objects.filter(
                customer=self
            ).aggregate(
                total=Sum('remaining_amount')
            )['total'] or Decimal('0')
            
            print(f"DEBUG: Updating balance for {self.name}: {total_outstanding}")
            
            # Only update if different to avoid unnecessary saves
            if self.outstanding_balance != total_outstanding:
                self.outstanding_balance = total_outstanding
                self.save(update_fields=['outstanding_balance'])
            
            return self.outstanding_balance
        except Exception as e:
            print(f"ERROR updating balance for {self.name}: {e}")
            return Decimal('0')

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
        
        print(f"DEBUG: Saving bill {self.bill_number}, paid: {self.paid_amount}, remaining: {self.remaining_amount}")
        
        # Save the bill first
        super().save(*args, **kwargs)
        
        # Then update customer balance
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
        print(f"DEBUG: Creating payment of ₹{self.amount} for {self.customer.name}")
        
        # Save payment first
        super().save(*args, **kwargs)
        
        # Update related bill if specified
        if self.bill:
            try:
                # Use atomic update to avoid race conditions
                from django.db import transaction
                with transaction.atomic():
                    bill = Bill.objects.select_for_update().get(id=self.bill.id)
                    old_paid = bill.paid_amount
                    bill.paid_amount += self.amount
                    
                    # Ensure paid_amount doesn't exceed total_amount
                    if bill.paid_amount > bill.total_amount:
                        bill.paid_amount = bill.total_amount
                    
                    # Update payment status based on new paid amount
                    if bill.paid_amount == 0:
                        bill.payment_status = 'pending'
                    elif bill.paid_amount >= bill.total_amount:
                        bill.payment_status = 'paid'
                        bill.remaining_amount = Decimal('0')
                    else:
                        bill.payment_status = 'partial'
                    
                    bill.remaining_amount = bill.total_amount - bill.paid_amount
                    
                    bill.save()
                    print(f"DEBUG: Updated bill {bill.bill_number}: paid_amount {old_paid} -> {bill.paid_amount}, status: {bill.payment_status}")
                    
            except Bill.DoesNotExist:
                print(f"ERROR: Bill {self.bill.id} not found")
        else:
            # If no specific bill, update all pending bills for this customer
            self.update_customer_pending_bills()
        
        # Update customer balance
        self.customer.update_balance()

    def update_customer_pending_bills(self):
        """Update all pending/partial bills for this customer when payment is received without specific bill"""
        try:
            from django.db import transaction
            with transaction.atomic():
                # Get all pending/partial bills for this customer, ordered by date (oldest first)
                pending_bills = Bill.objects.filter(
                    customer=self.customer,
                    payment_status__in=['pending', 'partial']
                ).order_by('date')
                
                remaining_amount = self.amount
                print(f"DEBUG: Distributing payment of ₹{remaining_amount} across {pending_bills.count()} pending bills")
                
                for bill in pending_bills:
                    if remaining_amount <= 0:
                        break
                        
                    bill_remaining = bill.remaining_amount
                    amount_to_pay = min(remaining_amount, bill_remaining)
                    
                    if amount_to_pay > 0:
                        old_paid = bill.paid_amount
                        bill.paid_amount += amount_to_pay
                        remaining_amount -= amount_to_pay
                        
                        # Update payment status
                        if bill.paid_amount >= bill.total_amount:
                            bill.payment_status = 'paid'
                            bill.remaining_amount = Decimal('0')
                        else:
                            bill.payment_status = 'partial'
                            bill.remaining_amount = bill.total_amount - bill.paid_amount
                        
                        bill.save()
                        print(f"DEBUG: Applied ₹{amount_to_pay} to bill {bill.bill_number}, new paid: {bill.paid_amount}, status: {bill.payment_status}")
                
                if remaining_amount > 0:
                    print(f"DEBUG: ₹{remaining_amount} remaining after paying all bills")
                    
        except Exception as e:
            print(f"ERROR in update_customer_pending_bills: {e}")

    def delete(self, *args, **kwargs):
        customer = self.customer
        bill = self.bill
        
        print(f"DEBUG: Deleting payment of ₹{self.amount} for {self.customer.name}")
        
        super().delete(*args, **kwargs)
        
        # Update bill if exists
        if bill:
            try:
                from django.db import transaction
                with transaction.atomic():
                    bill_refreshed = Bill.objects.select_for_update().get(id=bill.id)
                    old_paid = bill_refreshed.paid_amount
                    bill_refreshed.paid_amount -= self.amount
                    
                    # Ensure paid_amount doesn't go below 0
                    if bill_refreshed.paid_amount < 0:
                        bill_refreshed.paid_amount = Decimal('0')
                    
                    # Update payment status
                    if bill_refreshed.paid_amount == 0:
                        bill_refreshed.payment_status = 'pending'
                    elif bill_refreshed.paid_amount >= bill_refreshed.total_amount:
                        bill_refreshed.payment_status = 'paid'
                        bill_refreshed.remaining_amount = Decimal('0')
                    else:
                        bill_refreshed.payment_status = 'partial'
                    
                    bill_refreshed.remaining_amount = bill_refreshed.total_amount - bill_refreshed.paid_amount
                    
                    bill_refreshed.save()
                    print(f"DEBUG: Updated bill after deletion: {bill_refreshed.bill_number}: paid_amount {old_paid} -> {bill_refreshed.paid_amount}, status: {bill_refreshed.payment_status}")
                    
            except Bill.DoesNotExist:
                print(f"ERROR: Bill {bill.id} not found during deletion")
        
        # Update customer balance
        customer.update_balance()

    def __str__(self):
        return f"Payment of ₹{self.amount} from {self.customer.name}"
    

# Signals to handle balance updates automatically
@receiver(post_save, sender=Bill)
def update_customer_balance_on_bill_save(sender, instance, created, **kwargs):
    """Update customer balance when bill is saved"""
    print(f"SIGNAL: Bill {'created' if created else 'updated'} for {instance.customer.name}")
    instance.customer.update_balance()

@receiver(post_delete, sender=Bill)
def update_customer_balance_on_bill_delete(sender, instance, **kwargs):
    """Update customer balance when bill is deleted"""
    print(f"SIGNAL: Bill deleted for {instance.customer.name}")
    instance.customer.update_balance()

@receiver(post_save, sender=Payment)
def update_customer_balance_on_payment_save(sender, instance, created, **kwargs):
    """Update customer balance when payment is saved"""
    print(f"SIGNAL: Payment {'created' if created else 'updated'} for {instance.customer.name}")
    instance.customer.update_balance()

@receiver(post_delete, sender=Payment)
def update_customer_balance_on_payment_delete(sender, instance, **kwargs):
    """Update customer balance when payment is deleted"""
    print(f"SIGNAL: Payment deleted for {instance.customer.name}")
    instance.customer.update_balance()