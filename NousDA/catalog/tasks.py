from celery import shared_task
import bittensor
import logging
from django.db.models import Sum, Case, When, F, DecimalField
from bittensor.subtensor import Balance
import openpyxl
import pandas as pd
import csv
import yfinance
from .models import SingletonModel, Transaction, FIFOI, LIFOI, HIFOI, FIFOR, LIFOR, HIFOR
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction as db_transactions
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from django.conf import settings
import re
import os

from django.http import HttpResponse

from django.utils.timezone import localtime
from django.core.cache import cache

logger = logging.getLogger('catalog')


    
@shared_task(bind=True, priority=3)
def my_scheduled_task(self):

    wallet_address = "5H6VnWCi8wDV5xfatGtAbjkqiCtGoet7euCQNJTVjkL4LQcM"
    try:
        finney_subtensor = bittensor.subtensor(network="finney")
        historical_subtensor = bittensor.subtensor(network='archive')
        current_block = finney_subtensor.get_current_block()
    except Exception as e:
        logger.error(f"An error occurred while fetching the current block: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        else:
            logger.error("Max retries reached. Exiting task.")
            return
    try:
        singleton_instance = SingletonModel.objects.first()
        prev_block = singleton_instance.number
        prev_quantity = singleton_instance.prev_quantity
        prev_date = singleton_instance.date
    except Exception as e:
        logger.error(f"An error occurred while fetching the SingletonModel instance: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        else:
            logger.error("Max retries reached. Exiting task.")
            return

    price = 200
    saved_block = prev_block
    if current_block > prev_block:

        limit = min(current_block, prev_block + 1200)
        for block in range(prev_block + 1, limit):
        
            try:
                balance_str = historical_subtensor.get_balance(wallet_address, block=block)
            except Exception as e:

                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=60)
                else:

                    return
            
            new_balance = parse_balance(balance_str)

            transaction_date = prev_date + timedelta(seconds=12)
            try:
                with db_transactions.atomic():

                    if new_balance != prev_quantity:

                        new_price = get_price_for_date("TAO22974-USD", transaction_date)
                        price = new_price if new_price else price
                        transaction = create_transaction(new_balance, prev_quantity, price, block, transaction_date)
                        # 0.9444 - 300 = -299.056
                        # 299.056
                        amount_to_change = abs(new_balance - prev_quantity)
                        if new_balance > prev_quantity:  # Increase in assets
                            add_inventory(transaction, amount_to_change)
                        else:  # Decrease in assets
                            handle_inventory_changes(transaction, amount_to_change, price)

                    prev_quantity = new_balance
                    prev_date = transaction_date
                    saved_block = block
            except Exception as e:
                logger.error(f"An error occurred while processing the transaction: {str(e)}")
                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=60)
                else:
                    logger.error("Max retries reached. Exiting task.")
                    return

        singleton_instance.number = saved_block
        singleton_instance.prev_quantity = prev_quantity
        singleton_instance.date = prev_date
        singleton_instance.save()

def create_transaction(new_balance, prev_quantity, price, block, transaction_date):
    is_in = new_balance > prev_quantity
    transaction_amount = abs(new_balance - prev_quantity)
    
    return Transaction.objects.create(
        is_in=is_in,
        price=price,
        transaction_block=block,
        transaction_date=transaction_date,
        transaction_amount=transaction_amount
    )

def add_inventory(transaction, amount_to_add):
    # Here we would handle logic for adding inventory, such as creating new FIFO, LIFO, or HIFO entries
    FIFOI.objects.create(transaction=transaction, corrected_amount=None)
    LIFOI.objects.create(transaction=transaction, corrected_amount=None)
    HIFOI.objects.create(transaction=transaction, corrected_amount=None)

def handle_inventory_changes(transaction, amount_to_deduct, price):
    process_inventory_transaction(LIFOI, LIFOR, amount_to_deduct, price, transaction, reverse=True, isPrice=False)
    process_inventory_transaction(HIFOI, HIFOR, amount_to_deduct, price, transaction, reverse=False, isPrice=True)
    process_inventory_transaction(FIFOI, FIFOR, amount_to_deduct, price, transaction, reverse=False, isPrice=False)

def process_inventory_transaction(inventory_model, correction_model, amount_to_deduct, price, transaction, reverse=False, isPrice=False ):
    # amount to deduct is 299
    if isPrice:
        existing_inventory = inventory_model.objects.select_related('transaction').order_by('-transaction__price')
    else:
        existing_inventory = inventory_model.objects.select_related('transaction').order_by('-transaction__transaction_date' if reverse else 'transaction__transaction_date')
    for item in existing_inventory:
        if amount_to_deduct <= 0:
            break

        if item.corrected_amount is None:
            if item.transaction.transaction_amount <= amount_to_deduct:
                correction_model.objects.create(
                    transaction=item.transaction,
                    new_price=price
                )
                amount_to_deduct -= item.transaction.transaction_amount
                item.delete()
            else:
                item.corrected_amount = item.transaction.transaction_amount - amount_to_deduct
                item.save(update_fields=['corrected_amount'])
                correction_model.objects.create(
                    transaction=item.transaction,
                    new_price=price,
                    correct_amount=amount_to_deduct
                )
                amount_to_deduct = 0
        elif item.corrected_amount:
            if item.corrected_amount <= amount_to_deduct:
                correction_model.objects.create(
                    transaction=item.transaction,
                    new_price=price,
                    correct_amount=item.corrected_amount
                )
                amount_to_deduct -= item.corrected_amount
                item.delete()
            else:
                item.corrected_amount = item.corrected_amount - amount_to_deduct
                item.save(update_fields=['corrected_amount'])
                correction_model.objects.create(
                    transaction=item.transaction,
                    new_price=price,
                    correct_amount=amount_to_deduct
                )
                amount_to_deduct = 0

def get_price_for_date(asset_ticker, target):
    try:
        timezone = pytz.timezone(settings.TIME_ZONE)  # Ensure settings is imported
        ticker = yfinance.Ticker(asset_ticker)

        if settings.USE_TZ:
            target = timezone.localize(target) if target.tzinfo is None else target.astimezone(timezone)

        start_date = target - timedelta(days=1)
        end_date = target + timedelta(days=1)
    
    
        data = ticker.history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval='1d')

        if not data.empty:
            # Adjust timezone if data is timezone-aware
            if data.index.tz is None:
                data.index = data.index.tz_localize('UTC').tz_convert(timezone)
            elif data.index.tz != timezone:
                data.index = data.index.tz_convert(timezone)

            target_str = target.strftime('%Y-%m-%d')
            if target_str in data.index.strftime('%Y-%m-%d'):
                return Decimal(data.loc[target.strftime('%Y-%m-%d'), 'Close'])
            else:
                return Decimal(data['Close'].iloc[0])  # Return the closest available price
    except Exception as e:
        # Log the error and return None if any error occurs during fetching or processing
        print(f"An error occurred while fetching the price for {asset_ticker} on {target.strftime('%Y-%m-%d')}: {str(e)}")
        return None

    return None  # Return None if no data is available

def parse_balance(balance):
    """ Extract numeric value from the balance string or object and convert to Decimal. """
    return round(Decimal(balance.__float__()),9)  # Convert float to Decimal immediately

@shared_task
def export_inventory_to_excel(priority=0):
    # Collect data from your models with related transaction details
    fifo_data = FIFOI.objects.select_related('transaction').all()
    lifo_data = LIFOI.objects.select_related('transaction').all()
    hifo_data = HIFOI.objects.select_related('transaction').all()
    fifor_data = FIFOR.objects.select_related('transaction').all()
    lifor_data = LIFOR.objects.select_related('transaction').all()
    hifor_data = HIFOR.objects.select_related('transaction').all()
    datasets = [fifo_data, lifo_data, hifo_data, fifor_data, lifor_data, hifor_data]
    for dataset in datasets:
        if dataset.count() > 1000000:
            return HttpResponseBadRequest("Data too big for Excel. Please export to CSV instead.")

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

@shared_task
def export_inventory_to_csv(prioirity=0):
    transactions = Transaction.objects.all()

    # Prepare HTTP response object for CSV output
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_transactions_data.csv"'

    # Specify the field names based on the Transaction model
    fieldnames = [
        'transaction_id', 
        'is_in', 
        'price', 
        'transaction_block', 
        'transaction_date', 
        'transaction_amount'
    ]

    # Create a CSV writer object and write the headers and data
    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()

    # Serialize transaction data
    for transaction in transactions:
        transaction_data = {
            'transaction_id': str(transaction.transaction_id),  # Convert UUID to string
            'is_in': transaction.is_in,
            'price': transaction.price,
            'transaction_block': transaction.transaction_block,
            'transaction_date': localtime(transaction.transaction_date).strftime('%Y-%m-%d %H:%M:%S') if transaction.transaction_date else None,
            'transaction_amount': transaction.transaction_amount
        }
        writer.writerow(transaction_data)

    return response

def format_decimal(value):
    # This function will format the decimal value to two decimal places
    if value:
        return value.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
    return value
def apply_tax(value, tax_rate=0.27, gain_reduction=0.10):
    if value:
        if value<0:
            return format_decimal(value * Decimal(tax_rate) * Decimal(gain_reduction))
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

@shared_task
def update_cached_data():
    logger.debug("Updating cached data...")
    print("Continue to get better. Keep challenging yourself. Don't be afraid to succeed.")
   
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
    logger.debug("Fetching latest transaction...")


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

    logger.debug("Calculating inventory sums...")

    fifor_gain = format_decimal(calculate_gain_sum(FIFOR,'correct_amount', 'new_price'))
    lifor_gain = format_decimal(calculate_gain_sum(LIFOR, 'correct_amount','new_price'))
    hifor_gain = format_decimal(calculate_gain_sum(HIFOR, 'correct_amount','new_price'))

    logger.debug("I am a bad man and I think three steps ahead")

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
        'date': timezone.now(),
        'num_transactions': num_transactions,
        'num_transactions_in': num_transactions_in,
        'num_transactions_out': num_transactions_out,
        'latest_transaction': my_transaction_block,
        **inventory_sums,
        **gain_sums,
        **gain_taxes,
    }

    cache.set('dashboard_data', context, timeout=None)