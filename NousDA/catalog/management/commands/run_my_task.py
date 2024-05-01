from django.core.management.base import BaseCommand
from django.conf import settings
from catalog.tasks import test_task  # Assuming test_task is your Celery task
import bittensor
import yfinance
from datetime import datetime, timedelta
import pytz

class Command(BaseCommand):
    help = 'Runs the test_task Celery task'

    def handle(self, *args, **options):
        self.stdout.write("Running the Celery task...")
        result = test_task.delay()  # Using delay to asynchronously execute the task
        finney_subtensor = bittensor.subtensor(network="finney") # This is where to get the current block
        historical_subtensor = bittensor.subtensor(network = 'archive') # this is where to get the historical values. Important to test whether update to archive is instanttaneous
        current_block = finney_subtensor.get_current_block() # getting current block
        wallet_address = "5H6VnWCi8wDV5xfatGtAbjkqiCtGoet7euCQNJTVjkL4LQcM" # wallet address this is going to have to be more professional
        new_balance = historical_subtensor.get_balance(wallet_address, block=2213959)
        self.stdout.write(f"Current block: {current_block}")
        self.stdout.write(f"New balance: {new_balance}")
        self.stdout.write(f"Task enqueued: {result.id}")
        transaction_date = datetime(2024, 1, 1, 12, 0)
        ticker = yfinance.Ticker("TAO22974-USD") # getting the price of the asset
        new_price = get_price_for_date("TAO22974-USD", transaction_date) # getting the price of the asset
        self.stdout.write(f"New price: {new_price}")


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