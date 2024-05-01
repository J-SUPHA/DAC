from django.contrib import admin
from .models import Transaction, SingletonModel, LIFOI, LIFOR, HIFOI, HIFOR, FIFOI, FIFOR

# Register your models here.
admin.site.register(Transaction)
admin.site.register(SingletonModel)
admin.site.register(LIFOI)
admin.site.register(LIFOR)
admin.site.register(HIFOI)
admin.site.register(HIFOR)
admin.site.register(FIFOI)
admin.site.register(FIFOR)