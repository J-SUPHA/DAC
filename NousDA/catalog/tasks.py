from celery import shared_task
import bittensor
import yfinance
from .models import SingletonModel, Transaction, FIFOI, LIFOI, HIFOI, FIFOR, LIFOR, HIFOR
from django.db import transaction as db_transactions
from django.utils import timezone
from datetime import timedelta 
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
from django.conf import settings



@shared_task
def test_task():
    current_time = timezone.now()
    return f"Task was executed at {current_time}"


    
@shared_task
def my_scheduled_task():
    print('This is a scheduled task')

    finney_subtensor = bittensor.subtensor(network="finney") # This is where to get the current block
    historical_subtensor = bittensor.subtensor(network = 'archive') # this is where to get the historical values. Important to test whether update to archive is instanttaneous
    current_block = finney_subtensor.get_current_block() # getting current block
    wallet_address = "5H6VnWCi8wDV5xfatGtAbjkqiCtGoet7euCQNJTVjkL4LQcM" # wallet address this is going to have to be more professional

    singleton_instance = SingletonModel.objects.first() # getting the signnleton instance
    prev_block = singleton_instance.number # block number in the database
    prev_quantity = singleton_instance.prev_quantity # quantity of the database - number of assets
    prev_date = singleton_instance.date  # last date in datetime format
    price = 200

    if current_block > prev_block: # if the current block is greater than the previous block so if we are behind
        for block in range(prev_block + 1, current_block + 1): # we are going from the prev_block plus one to the final block
            new_balance = historical_subtensor.get_balance(wallet_address, block=block)  # getting the balance at the block

            transaction_date = prev_date + timedelta(seconds=12)

            ticker = yfinance.Ticker("TAO22974-USD") # getting the price of the asset
            new_price = get_price_for_date("TAO22974-USD", transaction_date) # getting the price of the asset
            if new_price is not None:
                price = new_price
            

            with db_transactions.atomic():
                if new_balance > prev_quantity: # if the new balance is greater than the previous quantity ie assets are coming in
                    

                    transaction = Transaction.objects.create( # create the transaction
                        is_in=True,
                        price=price,
                        transaction_block=block,
                        transaction_date= prev_date + timedelta(seconds=12),
                        transaction_amount=new_balance - prev_quantity
                    )

                    FIFOI.objects.create(transaction=transaction) # FIFOI object has an automatic field for the transactionID and the corrected amoutn is already set to None
                    LIFOI.objects.create(transaction=transaction)
                    HIFOI.objects.create(transaction=transaction)

                elif new_balance < prev_quantity:
                    transaction = Transaction.objects.create( # initializing the transaction make sure tto change the timeto use the singleton date
                        is_in=False,
                        price=price,
                        transaction_block=block,
                        transaction_date=transaction_date,
                        transaction_amount=prev_quantity - new_balance
                    )

                    amount_to_deduct = prev_quantity - new_balance # amount to deduct

                    # LIFO
                    lifo_transactions = LIFOI.objects.select_related('transaction').order_by('-transaction__transaction_date') # may need to change this to select everything instead of just selecting transaction
                    for lifo_transaction in lifo_transactions: # for each transaction in the LIFO
                        if amount_to_deduct <= 0: # if the amount to deduct is less than or equal to 0 then break
                            break

                        if lifo_transaction.corrected_amount is None: # case where the field in LIFO has not been altered. This is the case where the corrected amount is None
                            if lifo_transaction.transaction.transaction_amount <= amount_to_deduct:
                                LIFOR.objects.create(
                                    transaction=lifo_transaction.transaction,
                                    new_price=price
                                )
                                amount_to_deduct -= lifo_transaction.transaction.transaction_amount
                                lifo_transaction.delete()
                                # Get the row LIFOI and then put all of into the LIFOR table along with the new price no need for corrected amount
                                # reduce the amount to dedect by the transaction amount
                            else:
                                lifo_transaction.corrected_amount = lifo_transaction.transaction.transaction_amount - amount_to_deduct
                                lifo_transaction.save()
                                LIFOR.objects.create(
                                    transaction=lifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                                # amount left in LIFOI is going to be lifo_transaction.transaction.transaction_amount - amount_to_deduct 
                                # replace the corrected amount in the LIFOI table which is lifo.transaction.transaction_amount - amount_to_deduct 
                                # To the LIFOR table add the matching transaction from LIFOI and the new price and the the correct amount will be the amount to deduct
                                # reduce amount to deduct to zero 
                        elif lifo_transaction.corrected_amount:
                            if lifo_transaction.corrected_amount <= amount_to_deduct:
                                LIFOR.objects.create(
                                    transaction=lifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=lifo_transaction.corrected_amount
                                )
                                amount_to_deduct -= lifo_transaction.corrected_amount
                                lifo_transaction.delete()
                                # Get the row LIFOI including the associated transation field and then put all of into the LIFOR table along with a corect_amount field which is the same as the correct amount in LIFOI
                                # reduce the amount to dedect by the correct amount
                            else:
                                lifo_transaction.corrected_amount = lifo_transaction.corrected_amount - amount_to_deduct
                                lifo_transaction.save()
                                LIFOR.objects.create(
                                    transaction=lifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                                # amount left in LIFOI is going to be lifo_transaction.corrected_amount - amount_to_deduct 
                                # replace the corrected amount in  the LIFOI table which is lifo.corrected_amount - amount_to_deduct 
                                # To the LIFOR table add the matching transaction from LIFOI and the new price and the the correct amount will be the amount to deduct
                                # reduce amount to deduct to zero
                    hifo_transactions = HIFOI.objects.select_related('transaction').order_by('-transaction__price')
                    for hifo_transaction in hifo_transactions:
                        if amount_to_deduct <= 0:
                            break

                        if hifo_transaction.corrected_amount is None:
                            if hifo_transaction.transaction.transaction_amount <= amount_to_deduct:
                                HIFOR.objects.create(
                                    transaction=hifo_transaction.transaction,
                                    new_price=price
                                )
                                amount_to_deduct -= hifo_transaction.transaction.transaction_amount
                                hifo_transaction.delete()
                            else:
                                hifo_transaction.corrected_amount = hifo_transaction.transaction.transaction_amount - amount_to_deduct
                                hifo_transaction.save()
                                HIFOR.objects.create(
                                    transaction=hifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                        elif hifo_transaction.corrected_amount:
                            if hifo_transaction.corrected_amount <= amount_to_deduct:
                                HIFOR.objects.create(
                                    transaction=hifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=hifo_transaction.corrected_amount
                                )
                                amount_to_deduct -= hifo_transaction.corrected_amount
                                hifo_transaction.delete()
                            else:
                                hifo_transaction.corrected_amount = hifo_transaction.corrected_amount - amount_to_deduct
                                hifo_transaction.save()
                                HIFOR.objects.create(
                                    transaction=hifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                    fifo_transactions = FIFOI.objects.select_related('transaction').order_by('transaction__transaction_date')
                    for fifo_transaction in fifo_transactions:
                        if amount_to_deduct <= 0:
                            break

                        if fifo_transaction.corrected_amount is None:
                            if fifo_transaction.transaction.transaction_amount <= amount_to_deduct:
                                FIFOR.objects.create(
                                    transaction=fifo_transaction.transaction,
                                    new_price=price
                                )
                                amount_to_deduct -= fifo_transaction.transaction.transaction_amount
                                fifo_transaction.delete()
                            else:
                                fifo_transaction.corrected_amount = fifo_transaction.transaction.transaction_amount - amount_to_deduct
                                fifo_transaction.save()
                                FIFOR.objects.create(
                                    transaction=fifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                        elif fifo_transaction.corrected_amount:
                            if fifo_transaction.corrected_amount <= amount_to_deduct:
                                FIFOR.objects.create(
                                    transaction=fifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=fifo_transaction.corrected_amount
                                )
                                amount_to_deduct -= fifo_transaction.corrected_amount
                                fifo_transaction.delete()
                            else:
                                fifo_transaction.corrected_amount = fifo_transaction.corrected_amount - amount_to_deduct
                                fifo_transaction.save()
                                FIFOR.objects.create(
                                    transaction=fifo_transaction.transaction,
                                    new_price=price,
                                    correct_amount=amount_to_deduct
                                )
                                amount_to_deduct = 0
                prev_quantity = new_balance
                current_date = transaction_date

        singleton_instance.number = current_block
        singleton_instance.prev_quantity = prev_quantity
        singleton_instance.save()

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


