from orchestrator.models import PipelineType
from submitter import NextflowJobSubmitter, ToilJobSubmitter


class JobSubmitterFactory(object):

    @staticmethod
    def factory(type, job_id, app, inputs, root_dir, resume_jobstore=None):
        if type == PipelineType.CWL:
            return ToilJobSubmitter(job_id, app, inputs, root_dir, resume_jobstore)
        elif type == PipelineType.NEXTFLOW:
            return NextflowJobSubmitter(job_id, app, inputs, root_dir, resume_jobstore)
