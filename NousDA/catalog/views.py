from django.shortcuts import render
from django.db.models import Sum, Case, When, F, DecimalField
from .models import Transaction, SingletonModel, FIFOI, LIFOI, FIFOR, LIFOR, HIFOI, HIFOR
import pandas as pd 
from django.http import HttpResponse
import openpyxl


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
    num_transactions = Transaction.objects.count()
    num_transactions_in = Transaction.objects.filter(is_in=True).count()
    num_transactions_out = num_transactions - num_transactions_in

    # Calculate totals using utility functions
    inventory_sums = {
        'fifo': calculate_inventory_sum(FIFOI, "transaction__price", "corrected_amount"),
        'lifo': calculate_inventory_sum(LIFOI, "transaction__price", "corrected_amount"),
        'hifo': calculate_inventory_sum(HIFOI, "transaction__price", "corrected_amount"),
        'fifor': calculate_inventory_sum(FIFOR, "new_price","correct_amount"),
        'lifor': calculate_inventory_sum(LIFOR, "new_price","correct_amount"),
        'hifor': calculate_inventory_sum(HIFOR, "new_price","correct_amount"),
        'fifor_native': calculate_native_inventory_sum(FIFOR, 'correct_amount'),
        'lifor_native': calculate_native_inventory_sum(LIFOR, 'correct_amount'),
        'hifor_native': calculate_native_inventory_sum(HIFOR, 'correct_amount'),
        'fifo_native': calculate_native_inventory_sum(FIFOI, 'corrected_amount'),
        'lifo_native': calculate_native_inventory_sum(LIFOI, 'corrected_amount'),
        'hifo_native': calculate_native_inventory_sum(HIFOI, 'corrected_amount'),
    }

    gain_sums = {
        'fifor_gain': calculate_gain_sum(FIFOR,'correct_amount', 'new_price'),
        'lifor_gain': calculate_gain_sum(LIFOR, 'correct_amount','new_price'),
        'hifor_gain': calculate_gain_sum(HIFOR, 'correct_amount','new_price'),
    }

    context = {
        'num_transactions': num_transactions,
        'num_transactions_in': num_transactions_in,
        'num_transactions_out': num_transactions_out,
        **inventory_sums,
        **gain_sums,
    }

    return render(request, 'index.html', context)

def export_inventory_to_excel(request):
    # Collect data from your models
    fifo_data = list(FIFOI.objects.all().values())
    lifo_data = list(LIFOI.objects.all().values())
    hifo_data = list(HIFOI.objects.all().values())
    fifor_data = list(FIFOR.objects.all().values())
    lifor_data = list(LIFOR.objects.all().values())
    hifor_data = list(HIFOR.objects.all().values())

    # Convert data to pandas DataFrame
    fifo_df = pd.DataFrame(fifo_data)
    lifo_df = pd.DataFrame(lifo_data)
    hifo_df = pd.DataFrame(hifo_data)
    fifor_df = pd.DataFrame(fifor_data)
    lifor_df = pd.DataFrame(lifor_data)
    hifor_df = pd.DataFrame(hifor_data)

    # Create a Pandas Excel writer using openpyxl as the engine
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="inventory_data.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        fifo_df.to_excel(writer, sheet_name='FIFOI')
        lifo_df.to_excel(writer, sheet_name='LIFOI')
        hifo_df.to_excel(writer, sheet_name='HIFOI')
        fifor_df.to_excel(writer, sheet_name='FIFOR')
        lifor_df.to_excel(writer, sheet_name='LIFOR')
        hifor_df.to_excel(writer, sheet_name='HIFOR')

    return response
