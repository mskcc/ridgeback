from django.contrib import admin
from .models import Job, CommandLineToolJob


admin.site.register(Job)
admin.site.register(CommandLineToolJob)