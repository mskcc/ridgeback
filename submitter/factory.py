from orchestrator.models import PipelineType
from submitter import NextflowJobSubmitter, ToilJobSubmitter


class JobSubmitterFactory(object):
    @staticmethod
    def factory(
        type,
        job_id,
        app,
        inputs,
        root_dir,
        resume_jobstore=None,
        walltime=None,
        tool_walltime=None,
        memlimit=None,
        log_dir=None,
        app_name="NA",
    ):
        if type == PipelineType.CWL:
            return ToilJobSubmitter(
                job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit, log_dir, app_name
            )
        elif type == PipelineType.NEXTFLOW:
            return NextflowJobSubmitter(
                job_id, app, inputs, root_dir, resume_jobstore, walltime, tool_walltime, memlimit, log_dir, app_name
            )
