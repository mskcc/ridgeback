from django.contrib import admin
from .models import Job, CommandLineToolJob
from toil_orchestrator.tasks import cleanup_folders
from django.contrib import messages


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	actions = ['cleanup_files']
	report_message = """
	Cleaning up {cleaning} job(s) [{partial_cleaning} partial]
	Already cleaned up {cleaned_up}
	"""

	def cleanup_files(self, request, queryset):
		cleaned_up_projects = 0
		partially_cleaned_up_projects = 0
		already_cleaned_up_projects = 0
		for job in queryset:

			if all([job.job_store_clean_up, job.working_dir_clean_up]):
				cleaned_up_projects = cleaned_up_projects + 1
			elif any([job.job_store_clean_up, job.working_dir_clean_up]):
				cleaned_up_projects = cleaned_up_projects + 1
				partially_cleaned_up_projects = partially_cleaned_up_projects + 1
			else:
				already_cleaned_up_projects = already_cleaned_up_projects + 1

			cleanup_folders.delay(str(job.id))

		message = self.report_message.format(cleaning=cleaned_up_projects,
											 partial_cleaning=partially_cleaned_up_projects,
											 cleaned_up=already_cleaned_up_projects)

		self.message_user(request, message, level=messages.WARNING)

	cleanup_files.short_description = "Cleanup up the TOIL jobstore and workdir"
	list_display = ("id", "status", "created_date", "modified_date", "external_id")
	ordering = ('-created_date',)


@admin.register(CommandLineToolJob)
class CommandLineToolJobAdmin(admin.ModelAdmin):
	list_display = ("id", "job_name", "status", "created_date", "modified_date", "started", "submitted", "finished")
