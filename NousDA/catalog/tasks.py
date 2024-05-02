from celery import shared_task
import bittensor

from bittensor.subtensor import Balance
import yfinance
from .models import SingletonModel, Transaction, FIFOI, LIFOI, HIFOI, FIFOR, LIFOR, HIFOR
from django.db import transaction as db_transactions
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from django.conf import settings
import re




    
@shared_task
def my_scheduled_task():
    print('This is a scheduled task')

    finney_subtensor = bittensor.subtensor(network="finney")
    historical_subtensor = bittensor.subtensor(network='archive')
    current_block = finney_subtensor.get_current_block()
    current_block = 2215000
    wallet_address = "5H6VnWCi8wDV5xfatGtAbjkqiCtGoet7euCQNJTVjkL4LQcM"

    singleton_instance = SingletonModel.objects.first()
    prev_block = singleton_instance.number
    prev_quantity = singleton_instance.prev_quantity
    prev_date = singleton_instance.date
    price = 200

    if current_block > prev_block:
        for block in range(prev_block + 1, current_block + 1):
            balance_str = historical_subtensor.get_balance(wallet_address, block=block)
            new_balance = parse_balance(balance_str)
            transaction_date = prev_date + timedelta(seconds=12)
            new_price = get_price_for_date("TAO22974-USD", transaction_date)
            price = new_price if new_price else price

            with db_transactions.atomic():
                transaction = create_transaction(new_balance, prev_quantity, price, block, transaction_date)
                if new_balance != prev_quantity:
                    amount_to_change = abs(new_balance - prev_quantity)
                    if new_balance > prev_quantity:  # Increase in assets
                        add_inventory(transaction, amount_to_change)
                    else:  # Decrease in assets
                        handle_inventory_changes(transaction, amount_to_change, price)

                prev_quantity = new_balance
                prev_date = transaction_date

        singleton_instance.number = current_block
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
    process_inventory_transaction(LIFOI, LIFOR, amount_to_deduct, price, transaction, reverse=True)
    process_inventory_transaction(HIFOI, HIFOR, amount_to_deduct, price, transaction, reverse=False)
    process_inventory_transaction(FIFOI, FIFOR, amount_to_deduct, price, transaction, reverse=False)

def process_inventory_transaction(inventory_model, correction_model, amount_to_deduct, price, transaction, reverse=False):
    transactions = inventory_model.objects.select_related('transaction').order_by('-transaction__transaction_date' if reverse else 'transaction__transaction_date')
    for transaction in transactions:
        if amount_to_deduct <= 0:
            break

        if transaction.corrected_amount is None:
            if transaction.transaction.transaction_amount <= amount_to_deduct:
                correction_model.objects.create(
                    transaction=transaction.transaction,
                    new_price=price
                )
                amount_to_deduct -= transaction.transaction.transaction_amount
                transaction.delete()
            else:
                transaction.corrected_amount = transaction.transaction.transaction_amount - amount_to_deduct
                transaction.save()
                correction_model.objects.create(
                    transaction=transaction.transaction,
                    new_price=price,
                    correct_amount=amount_to_deduct
                )
                amount_to_deduct = 0
        elif transaction.corrected_amount:
            if transaction.corrected_amount <= amount_to_deduct:
                correction_model.objects.create(
                    transaction=transaction.transaction,
                    new_price=price,
                    correct_amount=transaction.corrected_amount
                )
                amount_to_deduct -= transaction.corrected_amount
                transaction.delete()
            else:
                transaction.corrected_amount = transaction.corrected_amount - amount_to_deduct
                transaction.save()
                correction_model.objects.create(
                    transaction=transaction.transaction,
                    new_price=price,
                    correct_amount=amount_to_deduct
                )
                amount_to_deduct = 0

def get_price_for_date(asset_ticker, target):
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
        try:
            # Access data safely
            if target_str in data.index.strftime('%Y-%m-%d'):
                return data.loc[target.strftime('%Y-%m-%d'), 'Close']
            else:
                return data['Close'].iloc[0]  # Return the closest available price
        except KeyError:
            # Handle the case where the date is still not found
            return None
    return None  # If no data is available, return None

def parse_balance(balance):
    """ Extract numeric value from the balance string or object and convert to Decimal. """
    return Decimal(balance.__float__())  # Convert float to Decimal immediately
