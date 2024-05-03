from django.db import models
from django.urls import reverse
import uuid


class Transaction(models.Model):
    transaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, help_text='Unique ID for this particular transaction')
    is_in = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    transaction_block = models.IntegerField()
    transaction_date = models.DateTimeField(null=True, blank=True)
    transaction_amount = models.DecimalField(max_digits=17, decimal_places=9)

    

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.transaction_id)])

    def __str__(self):
        return str(self.transaction_id)



class FIFOI(models.Model):
    input_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    corrected_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

    

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.input_key)])

    def __str__(self):
        return f'{self.transaction}'

class FIFOR(models.Model):
    output_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    new_price = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    correct_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

    

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.output_key)])

    def __str__(self):
        return f'{self.transaction}'

class LIFOI(models.Model):
    input_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    corrected_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

    

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.input_key)])

    def __str__(self):
        return f'{self.transaction}'

class LIFOR(models.Model):
    output_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    new_price = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    correct_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

   

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.output_key)])

    def __str__(self):
        return f'{self.transaction}'

class HIFOI(models.Model):
    input_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    corrected_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

    

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.input_key)])

    def __str__(self):
        return f'{self.transaction}'

class HIFOR(models.Model):
    output_key = models.AutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, help_text="Reference to the transaction")
    new_price = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    correct_amount = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)
    # other fields remain unchanged

   

    def get_absolute_url(self):
        return reverse('model-detail-view', args=[str(self.output_key)])

    def __str__(self):
        return f'{self.transaction}'

# Create your models here.
class SingletonModel(models.Model):
    """
    Model designed to only ever have one instance. Stores an atomic integer.
    """
    number = models.IntegerField(help_text="Current value of the atomic integer.")
    date = models.DateTimeField(auto_now=False, null=True, blank = True)
    prev_quantity = models.DecimalField(max_digits=17, decimal_places=9, null=True, blank=True)

    def clean(self):
        model = self.__class__
        if (model.objects.count() > 0 and
                self.id != model.objects.get().id):
            raise ValidationError("Can only create 1 %s instance" % model.__name__)

    def save(self, *args, **kwargs):
        self.full_clean()  # ensures the clean method is called
        super(SingletonModel, self).save(*args, **kwargs)

    def __str__(self):
        return str(self.number)