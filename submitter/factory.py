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
        leader_walltime=None,
        tool_walltime=None,
        memlimit=None,
        log_dir=None,
    ):
        if type == PipelineType.CWL:
            return ToilJobSubmitter(
                job_id, app, inputs, root_dir, resume_jobstore, leader_walltime, tool_walltime, memlimit, log_dir
            )
        elif type == PipelineType.NEXTFLOW:
            return NextflowJobSubmitter(
                job_id, app, inputs, root_dir, resume_jobstore, leader_walltime, tool_walltime, memlimit, log_dir
            )
