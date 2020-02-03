from django.contrib import admin
from .models import Job, CommandLineToolJob
from toil_orchestrator.tasks import cleanup_folder
from django.contrib import messages



@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	actions = ['cleanup_files']
	def cleanup_files(self, request, queryset):
		cleaned_up_projects = 0
		already_cleaned_up_projects = 0
		cleaned_up_message = None
		for single_query in queryset:
			jobstore_location = single_query.job_store_location
			working_dir = single_query.working_dir
			if not single_query.job_store_clean_up:
				cleanup_folder.delay(str(jobstore_location),single_query.id,True)
				cleanup_folder.delay(str(working_dir),single_query.id,False)
				cleaned_up_projects = cleaned_up_projects + 1
			else:
				already_cleaned_up_projects = already_cleaned_up_projects + 1
			if cleaned_up_projects > 0:
				cleaned_up_message = "Cleaned up %s job(s)" % cleaned_up_projects
				level = messages.SUCCESS
			if already_cleaned_up_projects > 0:
				if cleaned_up_message != None:
					cleaned_up_message = "%s , and already cleaned up %s job(s)" % (cleaned_up_message,already_cleaned_up_projects)
					level = messages.WARNING
				else:
					cleaned_up_message = "Already cleaned up %s job(s)" % already_cleaned_up_projects
					level = messages.ERROR
		self.message_user(request, cleaned_up_message,level=level)
	cleanup_files.short_description = "Cleanup up the TOIL jobstore and workdir"
	list_display = ("id", "status", "created_date", "modified_date", "external_id")

@admin.register(CommandLineToolJob)
class CommandLineToolJobAdmin(admin.ModelAdmin):
    list_display = ("id", "job_name", "status", "created_date", "modified_date", "started", "submitted", "finished")
