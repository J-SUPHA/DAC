from django.shortcuts import render
from django.db.models import Sum, Case, When, F, DecimalField
from .models import Transaction, SingletonModel, FIFOI, LIFOI, FIFOR, LIFOR, HIFOI, HIFOR
import pandas as pd 
from django.http import HttpResponse
from django.utils.timezone import localtime
import openpyxl
from decimal import Decimal, ROUND_HALF_UP
import csv
from django.http import JsonResponse
from .tasks import export_inventory_to_excel, export_inventory_to_csv

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
    if latest_transaction == 0:
        my_transaction_block = 0
    else:
        my_transaction_block = latest_transaction.transaction_block

    context = {
        'num_transactions': num_transactions,
        'num_transactions_in': num_transactions_in,
        'num_transactions_out': num_transactions_out,
        'latest_transaction': my_transaction_block,
        **inventory_sums,
        **gain_sums,
        **gain_taxes,
    }

    return render(request, 'index.html', context)


def trigger_excel_export(request):
    task = export_inventory_to_excel.delay()
    return JsonResponse({'status': 'Excel export started', 'task_id': task.id})

def trigger_csv_export(request):
    task = export_inventory_to_csv.delay()
    return JsonResponse({'status': 'CSV export started', 'task_id': task.id})