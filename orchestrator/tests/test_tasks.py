import uuid
from mock import patch, call
from django.test import TestCase
import tempfile
import os
from orchestrator.commands import CommandType, Command
from orchestrator.models import CommandLineToolJob
from orchestrator.models import Job, Status, PipelineType
from orchestrator.exceptions import RetryException, FetchStatusException
from orchestrator.tasks import (
    command_processor,
    check_job_status,
    process_jobs,
    cleanup_folders,
    get_job_info_path,
    set_permission,
)


class TasksTest(TestCase):
    def setUp(self):
        pass

    def test_status_transition(self):
        created = Status.CREATED
        self.assertFalse(created.transition(Status.CREATED))
        self.assertTrue(created.transition(Status.PREPARED))
        self.assertFalse(created.transition(Status.SUBMITTING))
        self.assertFalse(created.transition(Status.SUBMITTED))
        self.assertFalse(created.transition(Status.PENDING))
        self.assertFalse(created.transition(Status.RUNNING))
        self.assertFalse(created.transition(Status.COMPLETED))
        self.assertFalse(created.transition(Status.FAILED))
        self.assertTrue(created.transition(Status.TERMINATED))
        self.assertFalse(created.transition(Status.SUSPENDED))
        self.assertFalse(created.transition(Status.UNKNOWN))

        submitting = Status.SUBMITTING
        self.assertFalse(submitting.transition(Status.CREATED))
        self.assertFalse(submitting.transition(Status.PREPARED))
        self.assertFalse(submitting.transition(Status.SUBMITTING))
        self.assertTrue(submitting.transition(Status.SUBMITTED))
        self.assertFalse(submitting.transition(Status.PENDING))
        self.assertFalse(submitting.transition(Status.RUNNING))
        self.assertFalse(submitting.transition(Status.COMPLETED))
        self.assertFalse(submitting.transition(Status.FAILED))
        self.assertTrue(submitting.transition(Status.TERMINATED))
        self.assertFalse(submitting.transition(Status.SUSPENDED))
        self.assertFalse(submitting.transition(Status.UNKNOWN))

        submitted = Status.SUBMITTED
        self.assertFalse(submitted.transition(Status.CREATED))
        self.assertFalse(submitted.transition(Status.PREPARED))
        self.assertFalse(submitted.transition(Status.SUBMITTING))
        self.assertFalse(submitted.transition(Status.SUBMITTED))
        self.assertTrue(submitted.transition(Status.PENDING))
        self.assertTrue(submitted.transition(Status.RUNNING))
        self.assertTrue(submitted.transition(Status.COMPLETED))
        self.assertTrue(submitted.transition(Status.FAILED))
        self.assertTrue(submitted.transition(Status.TERMINATED))
        self.assertTrue(submitted.transition(Status.UNKNOWN))
        self.assertTrue(submitted.transition(Status.SUSPENDED))

        pending = Status.PENDING
        self.assertFalse(pending.transition(Status.CREATED))
        self.assertFalse(pending.transition(Status.PREPARED))
        self.assertFalse(pending.transition(Status.SUBMITTING))
        self.assertFalse(pending.transition(Status.SUBMITTED))
        self.assertTrue(pending.transition(Status.PENDING))
        self.assertTrue(pending.transition(Status.RUNNING))
        self.assertTrue(pending.transition(Status.COMPLETED))
        self.assertTrue(pending.transition(Status.FAILED))
        self.assertTrue(pending.transition(Status.TERMINATED))
        self.assertTrue(pending.transition(Status.UNKNOWN))
        self.assertTrue(pending.transition(Status.SUSPENDED))

        running = Status.RUNNING
        self.assertFalse(running.transition(Status.CREATED))
        self.assertFalse(running.transition(Status.PREPARED))
        self.assertFalse(running.transition(Status.SUBMITTING))
        self.assertFalse(running.transition(Status.SUBMITTED))
        self.assertFalse(running.transition(Status.PENDING))
        self.assertTrue(running.transition(Status.RUNNING))
        self.assertTrue(running.transition(Status.COMPLETED))
        self.assertTrue(running.transition(Status.FAILED))
        self.assertTrue(running.transition(Status.TERMINATED))
        self.assertTrue(running.transition(Status.UNKNOWN))
        self.assertTrue(running.transition(Status.SUSPENDED))

        terminated = Status.TERMINATED
        self.assertFalse(terminated.transition(Status.CREATED))
        self.assertFalse(terminated.transition(Status.PREPARED))
        self.assertFalse(terminated.transition(Status.SUBMITTING))
        self.assertFalse(terminated.transition(Status.SUBMITTED))
        self.assertFalse(terminated.transition(Status.PENDING))
        self.assertFalse(terminated.transition(Status.RUNNING))
        self.assertFalse(terminated.transition(Status.COMPLETED))
        self.assertFalse(terminated.transition(Status.FAILED))
        self.assertFalse(terminated.transition(Status.TERMINATED))
        self.assertFalse(terminated.transition(Status.UNKNOWN))
        self.assertFalse(terminated.transition(Status.SUSPENDED))

        suspended = Status.SUSPENDED
        self.assertFalse(suspended.transition(Status.CREATED))
        self.assertFalse(suspended.transition(Status.PREPARED))
        self.assertFalse(suspended.transition(Status.SUBMITTING))
        self.assertFalse(suspended.transition(Status.SUBMITTED))
        self.assertTrue(suspended.transition(Status.PENDING))
        self.assertTrue(suspended.transition(Status.RUNNING))
        self.assertFalse(suspended.transition(Status.COMPLETED))
        self.assertFalse(suspended.transition(Status.FAILED))
        self.assertTrue(suspended.transition(Status.TERMINATED))
        self.assertFalse(suspended.transition(Status.UNKNOWN))
        self.assertFalse(suspended.transition(Status.SUSPENDED))

        unknown = Status.UNKNOWN
        self.assertFalse(unknown.transition(Status.CREATED))
        self.assertFalse(unknown.transition(Status.PREPARED))
        self.assertFalse(unknown.transition(Status.SUBMITTING))
        self.assertFalse(unknown.transition(Status.SUBMITTED))
        self.assertTrue(unknown.transition(Status.PENDING))
        self.assertTrue(unknown.transition(Status.RUNNING))
        self.assertTrue(unknown.transition(Status.COMPLETED))
        self.assertTrue(unknown.transition(Status.FAILED))
        self.assertTrue(unknown.transition(Status.TERMINATED))
        self.assertTrue(unknown.transition(Status.UNKNOWN))
        self.assertTrue(unknown.transition(Status.SUSPENDED))

        completed = Status.COMPLETED
        self.assertFalse(completed.transition(Status.CREATED))
        self.assertFalse(completed.transition(Status.PREPARED))
        self.assertFalse(completed.transition(Status.SUBMITTING))
        self.assertFalse(completed.transition(Status.SUBMITTED))
        self.assertFalse(completed.transition(Status.PENDING))
        self.assertFalse(completed.transition(Status.RUNNING))
        self.assertFalse(completed.transition(Status.COMPLETED))
        self.assertFalse(completed.transition(Status.FAILED))
        self.assertFalse(completed.transition(Status.TERMINATED))
        self.assertFalse(completed.transition(Status.UNKNOWN))
        self.assertFalse(completed.transition(Status.SUSPENDED))

        failed = Status.FAILED
        self.assertFalse(failed.transition(Status.CREATED))
        self.assertFalse(failed.transition(Status.PREPARED))
        self.assertFalse(failed.transition(Status.SUBMITTING))
        self.assertFalse(failed.transition(Status.SUBMITTED))
        self.assertFalse(failed.transition(Status.PENDING))
        self.assertFalse(failed.transition(Status.RUNNING))
        self.assertFalse(failed.transition(Status.COMPLETED))
        self.assertFalse(failed.transition(Status.FAILED))
        self.assertFalse(failed.transition(Status.TERMINATED))
        self.assertFalse(failed.transition(Status.UNKNOWN))
        self.assertFalse(failed.transition(Status.SUSPENDED))

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    def test_check_status_unexisting_job(self, add, delete):
        add.return_value = True
        delete.return_value = True
        command_processor(Command(CommandType.SUBMIT, str(uuid.uuid4())).to_dict())

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_submitted_to_pending(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUBMITTED,
            metadata={"pipeline_name": "NA"},
        )
        status.return_value = Status.PENDING, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.PENDING)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_pending_to_running(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.PENDING,
            metadata={"pipeline_name": "NA"},
        )
        status.return_value = Status.RUNNING, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("submitter.toil_submitter.ToilJobSubmitter.get_outputs")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    @patch("orchestrator.tasks.set_permissions_job.delay")
    def test_running_to_completed(self, permission, status, get_outputs, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        permission.return_value = None
        status.return_value = Status.COMPLETED, ""
        outputs = {"output": "test_value"}
        get_outputs.return_value = outputs, None
        command_processor.return_value = None
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.COMPLETED)
        self.assertEqual(job.outputs, outputs)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_failed(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_failed_error_message_two_failed(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        failed_job_1 = CommandLineToolJob.objects.create(
            root=job, status=Status.FAILED, job_id="1", job_name="First Failed"
        )
        failed_job_2 = CommandLineToolJob.objects.create(
            root=job, status=Status.FAILED, job_id="2", job_name="Second Failed"
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        self.assertTrue(
            failed_job_1.job_name in job.message["failed_jobs"] and failed_job_2.job_name in job.message["failed_jobs"]
        )

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_failed_error_message_1_running(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        running_job_1 = CommandLineToolJob.objects.create(
            root=job, status=Status.RUNNING, job_id="1", job_name="First Running"
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        self.assertTrue(running_job_1.job_name in job.message["failed_jobs"])

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_failed_error_message_2_running(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        running_job_1 = CommandLineToolJob.objects.create(
            root=job, status=Status.RUNNING, job_id="1", job_name="First Running"
        )
        running_job_2 = CommandLineToolJob.objects.create(
            root=job, status=Status.RUNNING, job_id="2", job_name="Second Running"
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        failed_jobs = job.message["failed_jobs"]
        self.assertTrue(running_job_1.job_name not in failed_jobs and running_job_2.job_name in failed_jobs)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_failed_error_message_1_failed_2_running(self, status, command_processor):
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        failed_job_1 = CommandLineToolJob.objects.create(
            root=job, status=Status.FAILED, job_id="1", job_name="First Failed"
        )
        running_job_1 = CommandLineToolJob.objects.create(
            root=job, status=Status.RUNNING, job_id="1", job_name="First Running"
        )
        running_job_2 = CommandLineToolJob.objects.create(
            root=job, status=Status.RUNNING, job_id="2", job_name="Second Running"
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)
        failed_jobs = job.message["failed_jobs"]
        self.assertTrue(failed_job_1.job_name in failed_jobs and running_job_1.job_name not in failed_jobs)
        self.assertTrue(running_job_2.job_name in failed_jobs)

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("orchestrator.tasks.command_processor.delay")
    @patch("orchestrator.tasks.check_leader_not_running.delay")
    def test_process_jobs(self, check_leader_not_running, command_processor, add, delete):
        job_pending_1 = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.PENDING,
            metadata={"pipeline_name": "NA"},
        )
        job_created_1 = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.CREATED,
            metadata={"pipeline_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True

        process_jobs()
        calls = [
            call(Command(CommandType.CHECK_STATUS_ON_LSF, str(job_pending_1.id)).to_dict()),
            call(Command(CommandType.PREPARE, str(job_created_1.id)).to_dict()),
        ]

        command_processor.assert_has_calls(calls, any_order=True)
        check_leader_not_running.assert_called_once()

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_check_status_command_processor(self, status, add, delete):
        def _raise_retryable_exception(job_id):
            raise FetchStatusException("Error")

        job_pending_1 = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.PENDING,
            metadata={"pipeline_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True
        status.side_effect = _raise_retryable_exception
        with self.assertRaises(RetryException):
            command_processor(Command(CommandType.CHECK_STATUS_ON_LSF, str(job_pending_1.id)).to_dict())

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.terminate")
    def test_command_processor_term(self, terminate, add, delete):
        job_pending = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.PENDING,
            metadata={"pipeline_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True
        terminate.return_value = True
        command_processor(Command(CommandType.TERMINATE, str(job_pending.id)).to_dict())
        job_pending.refresh_from_db()
        self.assertEqual(job_pending.status, Status.TERMINATED)

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.suspend")
    def test_command_processor_suspend(self, suspend, add, delete):
        job_running = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.RUNNING,
            metadata={"pipeline_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True
        suspend.return_value = True
        command_processor(Command(CommandType.SUSPEND, str(job_running.id)).to_dict())
        job_running.refresh_from_db()
        self.assertEqual(job_running.status, Status.SUSPENDED)

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.resume")
    def test_command_processor_resume(self, suspend, add, delete):
        job_suspended = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUSPENDED,
            metadata={"pipeline_name": "NA"},
        )
        add.return_value = True
        delete.return_value = True
        suspend.return_value = True
        command_processor(Command(CommandType.RESUME, str(job_suspended.id)).to_dict())
        job_suspended.refresh_from_db()
        self.assertEqual(job_suspended.status, Status.RUNNING)

    @patch("orchestrator.tasks.clean_directory")
    def test_cleanup_folders(self, clean_directory):
        cleanup_job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.FAILED,
            metadata={"pipeline_name": "NA"},
        )
        clean_directory.return_value = True
        cleanup_folders(str(cleanup_job.id), exclude=[])
        cleanup_job.refresh_from_db()
        self.assertIsNotNone(cleanup_job.job_store_clean_up)
        self.assertIsNotNone(cleanup_job.job_store_clean_up)

    def test_get_job_info_path(self):
        PIPELINE_CONFIG = {
            "TEST": {
                "JOB_STORE_ROOT": "/toil/work/dir/root",
                "WORK_DIR_ROOT": "/toil/work/dir/root",
                "TMP_DIR_ROOT": "/toil/work/dir/root",
            },
        }
        job = Job.objects.create(
            type=PipelineType.CWL,
            app={
                "github": {
                    "version": "1.0.0",
                    "entrypoint": "test.cwl",
                    "repository": "",
                }
            },
            external_id="ext_id",
            status=Status.SUBMITTED,
            metadata={"pipeline_name": "TEST"},
        )
        with self.settings(PIPELINE_CONFIG=PIPELINE_CONFIG):
            res = get_job_info_path(str(job.id))
            self.assertEqual(res, f"/toil/work/dir/root/{str(job.id)}/.run.info")

    def test_permission(self):
        with tempfile.TemporaryDirectory() as temp_path:
            expected_permission = "750"
            job_completed = Job.objects.create(
                type=PipelineType.CWL,
                app={
                    "github": {
                        "version": "1.0.0",
                        "entrypoint": "test.cwl",
                        "repository": "",
                    }
                },
                root_dir=temp_path,
                base_dir="/".join(temp_path.split("/")[:-1]) + "/",
                root_permission=expected_permission,
                external_id="ext_id",
                status=Status.COMPLETED,
                metadata={"pipeline_name": "NA"},
            )
            set_permission(job_completed)
            current_permission = oct(os.stat(temp_path).st_mode)[-3:]
            self.assertEqual(current_permission, expected_permission)

    def test_permission_wrong_permission(self):
        with self.assertRaises(TypeError):
            with tempfile.TemporaryDirectory() as temp_path:
                expected_permission = "auk"
                job_completed = Job.objects.create(
                    type=PipelineType.CWL,
                    app={
                        "github": {
                            "version": "1.0.0",
                            "entrypoint": "test.cwl",
                            "repository": "",
                        }
                    },
                    root_dir=temp_path,
                    base_dir="/".join(temp_path.split("/")[:-1]) + "/",
                    root_permission=expected_permission,
                    external_id="ext_id",
                    status=Status.COMPLETED,
                    metadata={"pipeline_name": "NA"},
                )
                set_permission(job_completed)

    def test_permission_wrong_path(self):
        with self.assertRaises(RuntimeError):
            expected_permission = "750"
            job_completed = Job.objects.create(
                type=PipelineType.CWL,
                app={
                    "github": {
                        "version": "1.0.0",
                        "entrypoint": "test.cwl",
                        "repository": "",
                    }
                },
                root_dir="/awk",
                root_permission=expected_permission,
                external_id="ext_id",
                status=Status.COMPLETED,
                metadata={"pipeline_name": "NA"},
            )
            set_permission(job_completed)
