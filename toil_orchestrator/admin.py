from django.contrib import admin
from .models import Job, CommandLineToolJob

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	list_display = ("id","status","created_date","modified_date","external_id")

@admin.register(CommandLineToolJob)
class CommandLineToolJobAdmin(admin.ModelAdmin):
	list_display = ("id","job_name","status","created_date","modified_date","started","submitted","finished")