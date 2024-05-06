from django.shortcuts import render
from django.db.models import Sum, Case, When, F, DecimalField
from .models import Transaction, SingletonModel, FIFOI, LIFOI, FIFOR, LIFOR, HIFOI, HIFOR
import pandas as pd 
from django.http import HttpResponse
from django.utils.timezone import localtime
import openpyxl
from decimal import Decimal, ROUND_HALF_UP
import csv

def format_decimal(value):
    # This function will format the decimal value to two decimal places
    if value:
        return value.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    return value
def apply_tax(value, tax_rate=0.23):
    if value:
        return format_decimal(value * Decimal(tax_rate))
    return value

def calculate_inventory_sum(model, price_field, amount_field_1 ,amount_field_2='transaction__transaction_amount'):
    if amount_field_1 == 'correct_amount':
        return model.objects.annotate(
            total_value=Case(
                When(correct_amount__isnull=False,
                     then=F(amount_field_1) * F(price_field)),
                default=F(amount_field_2) * F(price_field),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']
    else:
        return model.objects.annotate(
            total_value=Case(
                When(corrected_amount__isnull=False,
                    then=F(amount_field_1) * F(price_field)),
                default=F(amount_field_2) * F(price_field),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']

def calculate_native_inventory_sum(model, amount_field_1):
    if amount_field_1 == 'correct_amount':
        return model.objects.annotate(
            total_value=Case(
                When(correct_amount__isnull=False,
                     then=F(amount_field_1)),
                default=F('transaction__transaction_amount'),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']
    else:
        return model.objects.annotate(
            total_value=Case(
                When(corrected_amount__isnull=False,
                    then=F(amount_field_1)),
                default=F('transaction__transaction_amount'),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']


def calculate_gain_sum(model, amount_field, price_field, price_diff_field='transaction__price'):
    if amount_field == 'correct_amount':
        return model.objects.annotate(
            total_value=Case(
                When(correct_amount__isnull=False,
                     then=F(amount_field) * (F(price_field) - F(price_diff_field))),
                default=F('transaction__transaction_amount') * (F(price_field) - F(price_diff_field)),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']
    else:
        return model.objects.annotate(
            total_value=Case(
                When(corrected_amount__isnull=False,
                    then=F(amount_field) * (F(price_field) - F(price_diff_field))),
                default=F('transaction__transaction_amount') * (F(price_field) - F(price_diff_field)),
                output_field=DecimalField(max_digits=20, decimal_places=7)
            )
        ).aggregate(total=Sum('total_value'))['total']


def index(request):
    try:
        latest_transaction = Transaction.objects.latest('transaction_block')
        num_transactions = Transaction.objects.count()
        num_transactions_in = Transaction.objects.filter(is_in=True).count()
        num_transactions_out = num_transactions - num_transactions_in
    except Transaction.DoesNotExist:
        latest_transaction = 0
        num_transactions = 0
        num_transactions_in = 0
        num_transactions_out = 0
    
    # Calculate totals using utility functions
    inventory_sums = {
        'fifo': format_decimal(calculate_inventory_sum(FIFOI, "transaction__price", "corrected_amount")),
        'lifo': format_decimal(calculate_inventory_sum(LIFOI, "transaction__price", "corrected_amount")),
        'hifo': format_decimal(calculate_inventory_sum(HIFOI, "transaction__price", "corrected_amount")),
        'fifor': format_decimal(calculate_inventory_sum(FIFOR, "new_price","correct_amount")),
        'lifor': format_decimal(calculate_inventory_sum(LIFOR, "new_price","correct_amount")),
        'hifor': format_decimal(calculate_inventory_sum(HIFOR, "new_price","correct_amount")),
        'fifor_native': format_decimal(calculate_native_inventory_sum(FIFOR, 'correct_amount')),
        'lifor_native': format_decimal(calculate_native_inventory_sum(LIFOR, 'correct_amount')),
        'hifor_native': format_decimal(calculate_native_inventory_sum(HIFOR, 'correct_amount')),
        'fifo_native': format_decimal(calculate_native_inventory_sum(FIFOI, 'corrected_amount')),
        'lifo_native': format_decimal(calculate_native_inventory_sum(LIFOI, 'corrected_amount')),
        'hifo_native': format_decimal(calculate_native_inventory_sum(HIFOI, 'corrected_amount')),
    }

    fifor_gain = format_decimal(calculate_gain_sum(FIFOR,'correct_amount', 'new_price'))
    lifor_gain = format_decimal(calculate_gain_sum(LIFOR, 'correct_amount','new_price'))
    hifor_gain = format_decimal(calculate_gain_sum(HIFOR, 'correct_amount','new_price'))

    print("This is my type ", type(inventory_sums['fifo_native']))
    gain_sums = {
        'fifor_gain': fifor_gain,
        'lifor_gain': lifor_gain,
        'hifor_gain': hifor_gain,
    }
    gain_taxes = {
        'fifor_gain_tax': apply_tax(fifor_gain),
        'lifor_gain_tax': apply_tax(lifor_gain),
        'hifor_gain_tax': apply_tax(hifor_gain),
    }

    context = {
        'num_transactions': num_transactions,
        'num_transactions_in': num_transactions_in,
        'num_transactions_out': num_transactions_out,
        'latest_transaction': latest_transaction.transaction_block,
        **inventory_sums,
        **gain_sums,
        **gain_taxes,
    }

    return render(request, 'index.html', context)



def export_inventory_to_excel(request):
    # Collect data from your models with related transaction details
    fifo_data = FIFOI.objects.select_related('transaction').all()
    lifo_data = LIFOI.objects.select_related('transaction').all()
    hifo_data = HIFOI.objects.select_related('transaction').all()
    fifor_data = FIFOR.objects.select_related('transaction').all()
    lifor_data = LIFOR.objects.select_related('transaction').all()
    hifor_data = HIFOR.objects.select_related('transaction').all()

    # Prepare data for DataFrame conversion
    def prepare_data(items):
        return [{
            'Input/Output Key': item.pk,
            'Transaction ID': item.transaction.transaction_id,
            'Is In': item.transaction.is_in,
            'Price': item.transaction.price,
            'Transaction Block': item.transaction.transaction_block,
            'Transaction Date': localtime(item.transaction.transaction_date).strftime('%Y-%m-%d %H:%M:%S') if item.transaction.transaction_date else None,
            'Transaction Amount': item.transaction.transaction_amount,
            'Corrected Amount/Correct Amount': getattr(item, 'corrected_amount', getattr(item, 'correct_amount', None)),
            'New Price': getattr(item, 'new_price', None)
        } for item in items]

    # Convert data to pandas DataFrame
    fifo_df = pd.DataFrame(prepare_data(fifo_data))
    lifo_df = pd.DataFrame(prepare_data(lifo_data))
    hifo_df = pd.DataFrame(prepare_data(hifo_data))
    fifor_df = pd.DataFrame(prepare_data(fifor_data))
    lifor_df = pd.DataFrame(prepare_data(lifor_data))
    hifor_df = pd.DataFrame(prepare_data(hifor_data))

    # Create a Pandas Excel writer using openpyxl as the engine
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="inventory_data.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        fifo_df.to_excel(writer, sheet_name='FIFOI')
        lifo_df.to_excel(writer, sheet_name='LIFOI')
        hifo_df.to_excel(writer, sheet_name='HIFOI')
        fifor_df.to_excel(writer, sheet_name='FIFOR')
        lifor_df.to_excel(writer, sheet_name='LIFOR')
        hifor_df.to_excel(writer, sheet_name='HIFOR')

    return response

def export_inventory_to_csv(request):
    # Collect data from your models with related transaction details
    fifo_data = FIFOI.objects.select_related('transaction').all()
    lifo_data = LIFOI.objects.select_related('transaction').all()
    hifo_data = HIFOI.objects.select_related('transaction').all()
    fifor_data = FIFOR.objects.select_related('transaction').all()
    lifor_data = LIFOR.objects.select_related('transaction').all()
    hifor_data = HIFOR.objects.select_related('transaction').all()

    # Prepare data for CSV conversion
    def prepare_data(items):
        return [
            {
                'Input/Output Key': item.pk,
                'Transaction ID': item.transaction.transaction_id,
                'Is In': item.transaction.is_in,
                'Price': item.transaction.price,
                'Transaction Block': item.transaction.transaction_block,
                'Transaction Date': localtime(item.transaction.transaction_date).strftime('%Y-%m-%d %H:%M:%S') if item.transaction.transaction_date else None,
                'Transaction Amount': item.transaction.transaction_amount,
                'Corrected Amount/Correct Amount': getattr(item, 'corrected_amount', getattr(item, 'correct_amount', None)),
                'New Price': getattr(item, 'new_price', None)
            } for item in items
        ]

    # Prepare HTTP response object for CSV output
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_data.csv"'

    # Create a CSV writer object and write the headers and data
    writer = csv.DictWriter(response, fieldnames=[
        'Input/Output Key', 'Transaction ID', 'Is In', 'Price', 'Transaction Block',
        'Transaction Date', 'Transaction Amount', 'Corrected Amount/Correct Amount', 'New Price'
    ])
    writer.writeheader()

    for model_data in [fifo_data, lifo_data, hifo_data, fifor_data, lifor_data, hifor_data]:
        prepared_data = prepare_data(model_data)
        for data in prepared_data:
            writer.writerow(data)

    return response