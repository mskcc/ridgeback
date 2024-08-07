from django.contrib import admin
from .models import Job, CommandLineToolJob, Status
from django.contrib import messages
from orchestrator.commands import CommandType, Command
from orchestrator.tasks import cleanup_folders, command_processor


class StatusFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        filters = {
            k: v
            for (k, v) in request.GET.items()
            if "range" not in k and "status" not in k and "q" not in k and "p" not in k
        }

        qs = model_admin.get_queryset(request).filter(**filters)
        return [
            (
                status.value,
                "%s (%s)" % (status.name, qs.filter(status=status.value).count()),
            )
            for status in Status
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_date", "modified_date", "external_id")
    ordering = ("-created_date",)
    list_filter = (StatusFilter,)

    actions = ["cleanup_files", "suspend", "resume"]

    def cleanup_files(self, request, queryset):
        cleaned_up_projects = 0
        partially_cleaned_up_projects = 0
        already_cleaned_up_projects = 0
        report_message = """
Cleaning up {cleaning} job(s) [{partial_cleaning} partial]
Already cleaned up {cleaned_up}
        """
        for job in queryset:
            if all([job.job_store_clean_up, job.working_dir_clean_up]):
                already_cleaned_up_projects = already_cleaned_up_projects + 1
            elif any([job.job_store_clean_up, job.working_dir_clean_up]):
                already_cleaned_up_projects = already_cleaned_up_projects + 1
                partially_cleaned_up_projects = partially_cleaned_up_projects + 1
            else:
                cleaned_up_projects = cleaned_up_projects + 1
                cleanup_folders.delay(str(job.id), exclude=[])

            message = report_message.format(
                cleaning=cleaned_up_projects,
                partial_cleaning=partially_cleaned_up_projects,
                cleaned_up=already_cleaned_up_projects,
            )

            self.message_user(request, message, level=messages.WARNING)

    def suspend(self, request, queryset):
        for job in queryset:
            if job.external_id:
                command_processor.delay(Command(CommandType.SUSPEND, str(job.id)).to_dict())

    def resume(self, request, queryset):
        for job in queryset:
            if job.external_id:
                command_processor.delay(Command(CommandType.RESUME, str(job.id)).to_dict())

    suspend.short_description = "Suspend Jobs"
    resume.short_description = "Resume Jobs"
    cleanup_files.short_description = "Cleanup up the TOIL jobstore and workdir"


@admin.register(CommandLineToolJob)
class CommandLineToolJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_name",
        "status",
        "created_date",
        "modified_date",
        "started",
        "submitted",
        "finished",
    )
