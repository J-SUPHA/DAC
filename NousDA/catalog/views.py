from django.shortcuts import render
from django.core.cache import cache


from django.http import HttpResponse

from django.http import JsonResponse
from .tasks import export_inventory_to_excel, export_inventory_to_csv

def index(request):
    data = cache.get('dashboard_data')
    if not data:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # AJAX request check
            return JsonResponse({})  # Return empty JSON for AJAX requests
        return render(request, 'index.html', {'data': {}})
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(data)  # Return JSON data for AJAX requests
    return render(request, 'index.html', {'data': data})


def trigger_excel_export(request):
    task = export_inventory_to_excel.delay()
    return JsonResponse({'status': 'Excel export started', 'task_id': task.id})

def trigger_csv_export(request):
    task = export_inventory_to_csv.delay()
    return JsonResponse({'status': 'CSV export started', 'task_id': task.id})