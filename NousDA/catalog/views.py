from django.shortcuts import render
from .models import Transaction, SingletonModel

# Create your views here.

def index(request):
    """View function for the home page of site """
    num_transactions = Transaction.objects.all().count()
    num_transactions_in = Transaction.objects.filter(is_in=True).count()
    num_transactions_out = Transaction.objects.filter(is_in=False).count()

    context = {
        'number_of_transactions': num_transactions,
        'number_of_transactions_in': num_transactions_in,
        'number_of_transactions_out': num_transactions_out,
    }

    return render(request, 'index.html', context=context)