from celery import shared_task
import bittensor
import logging
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
import os

logger = logging.getLogger('catalog')


    
@shared_task(bind=True)
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
    logger.debug("entering the loop")
    logger.debug(f"Current block: {current_block}")
    logger.debug(f"Previous block: {prev_block}")
    if current_block > prev_block:
        logger.debug("Pass through the loop")
        for block in range(prev_block + 1, current_block + 1):
            logger.debug(f"Fetching balance for address: {wallet_address}, block: {block}")
            try:
                balance_str = historical_subtensor.get_balance(wallet_address, block=block)
            except Exception as e:
                logger.error(f"An error occurred while fetching the balance for block {block}: {str(e)}")
                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=60)
                else:
                    logger.error("Max retries reached. Exiting task.")
                    return
            
            new_balance = parse_balance(balance_str)
            logger.debug(f"Received balance: {new_balance}")
            transaction_date = prev_date + timedelta(seconds=12)

            with db_transactions.atomic():

                if new_balance != prev_quantity:

                    logger.debug(f"New Balance: {new_balance}")
                    logger.debug(f"Previous Quantity: {prev_quantity}")

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

        singleton_instance.number = current_block
        logger.debug(f"Updating block to {prev_quantity}")
        singleton_instance.prev_quantity = prev_quantity
        singleton_instance.date = prev_date
        singleton_instance.save()

def create_transaction(new_balance, prev_quantity, price, block, transaction_date):
    is_in = new_balance > prev_quantity
    transaction_amount = abs(new_balance - prev_quantity)
    logger.debug(f"Creating transaction with values: {is_in}, {price}, {block}, {transaction_date}, {transaction_amount}")
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
