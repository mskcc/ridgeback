import uuid
from mock import patch, call
from django.test import TestCase
import tempfile
import os
from orchestrator.commands import CommandType, Command
from orchestrator.models import Job, Status, PipelineType
from orchestrator.exceptions import RetryException
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
        self.assertTrue(created.transition(Status.SUBMITTING))
        self.assertFalse(created.transition(Status.SUBMITTED))
        self.assertFalse(created.transition(Status.PENDING))
        self.assertFalse(created.transition(Status.RUNNING))
        self.assertFalse(created.transition(Status.COMPLETED))
        self.assertFalse(created.transition(Status.FAILED))
        self.assertTrue(created.transition(Status.ABORTED))
        self.assertFalse(created.transition(Status.SUSPENDED))
        self.assertFalse(created.transition(Status.UNKNOWN))

        submitting = Status.SUBMITTING
        self.assertFalse(submitting.transition(Status.CREATED))
        self.assertFalse(submitting.transition(Status.SUBMITTING))
        self.assertTrue(submitting.transition(Status.SUBMITTED))
        self.assertFalse(submitting.transition(Status.PENDING))
        self.assertFalse(submitting.transition(Status.RUNNING))
        self.assertFalse(submitting.transition(Status.COMPLETED))
        self.assertFalse(submitting.transition(Status.FAILED))
        self.assertTrue(submitting.transition(Status.ABORTED))
        self.assertFalse(submitting.transition(Status.SUSPENDED))
        self.assertFalse(submitting.transition(Status.UNKNOWN))

        submited = Status.SUBMITTED
        self.assertFalse(submited.transition(Status.CREATED))
        self.assertFalse(submited.transition(Status.SUBMITTING))
        self.assertFalse(submited.transition(Status.SUBMITTED))
        self.assertTrue(submited.transition(Status.PENDING))
        self.assertTrue(submited.transition(Status.RUNNING))
        self.assertTrue(submited.transition(Status.COMPLETED))
        self.assertTrue(submited.transition(Status.FAILED))
        self.assertTrue(submited.transition(Status.ABORTED))
        self.assertTrue(submited.transition(Status.UNKNOWN))
        self.assertTrue(submited.transition(Status.SUSPENDED))

        pending = Status.PENDING
        self.assertFalse(pending.transition(Status.CREATED))
        self.assertFalse(pending.transition(Status.SUBMITTING))
        self.assertFalse(pending.transition(Status.SUBMITTED))
        self.assertTrue(pending.transition(Status.PENDING))
        self.assertTrue(pending.transition(Status.RUNNING))
        self.assertTrue(pending.transition(Status.COMPLETED))
        self.assertTrue(pending.transition(Status.FAILED))
        self.assertTrue(pending.transition(Status.ABORTED))
        self.assertTrue(pending.transition(Status.UNKNOWN))
        self.assertTrue(pending.transition(Status.SUSPENDED))

        running = Status.RUNNING
        self.assertFalse(running.transition(Status.CREATED))
        self.assertFalse(running.transition(Status.SUBMITTING))
        self.assertFalse(running.transition(Status.SUBMITTED))
        self.assertFalse(running.transition(Status.PENDING))
        self.assertTrue(running.transition(Status.RUNNING))
        self.assertTrue(running.transition(Status.COMPLETED))
        self.assertTrue(running.transition(Status.FAILED))
        self.assertTrue(running.transition(Status.ABORTED))
        self.assertTrue(running.transition(Status.UNKNOWN))
        self.assertTrue(running.transition(Status.SUSPENDED))

        aborted = Status.ABORTED
        self.assertFalse(aborted.transition(Status.CREATED))
        self.assertFalse(aborted.transition(Status.SUBMITTING))
        self.assertFalse(aborted.transition(Status.SUBMITTED))
        self.assertFalse(aborted.transition(Status.PENDING))
        self.assertFalse(aborted.transition(Status.RUNNING))
        self.assertFalse(aborted.transition(Status.COMPLETED))
        self.assertFalse(aborted.transition(Status.FAILED))
        self.assertFalse(aborted.transition(Status.ABORTED))
        self.assertFalse(aborted.transition(Status.UNKNOWN))
        self.assertFalse(aborted.transition(Status.SUSPENDED))

        suspended = Status.SUSPENDED
        self.assertFalse(suspended.transition(Status.CREATED))
        self.assertFalse(suspended.transition(Status.SUBMITTING))
        self.assertFalse(suspended.transition(Status.SUBMITTED))
        self.assertTrue(suspended.transition(Status.PENDING))
        self.assertTrue(suspended.transition(Status.RUNNING))
        self.assertFalse(suspended.transition(Status.COMPLETED))
        self.assertFalse(suspended.transition(Status.FAILED))
        self.assertTrue(suspended.transition(Status.ABORTED))
        self.assertFalse(suspended.transition(Status.UNKNOWN))
        self.assertFalse(suspended.transition(Status.SUSPENDED))

        unknown = Status.UNKNOWN
        self.assertFalse(unknown.transition(Status.CREATED))
        self.assertFalse(unknown.transition(Status.SUBMITTING))
        self.assertFalse(unknown.transition(Status.SUBMITTED))
        self.assertTrue(unknown.transition(Status.PENDING))
        self.assertTrue(unknown.transition(Status.RUNNING))
        self.assertTrue(unknown.transition(Status.COMPLETED))
        self.assertTrue(unknown.transition(Status.FAILED))
        self.assertTrue(unknown.transition(Status.ABORTED))
        self.assertTrue(unknown.transition(Status.UNKNOWN))
        self.assertTrue(unknown.transition(Status.SUSPENDED))

        completed = Status.COMPLETED
        self.assertFalse(completed.transition(Status.RUNNING))
        self.assertFalse(completed.transition(Status.COMPLETED))
        self.assertFalse(completed.transition(Status.FAILED))
        self.assertFalse(completed.transition(Status.ABORTED))
        self.assertFalse(completed.transition(Status.SUSPENDED))
        self.assertFalse(completed.transition(Status.UNKNOWN))
        self.assertFalse(completed.transition(Status.PENDING))
        self.assertFalse(completed.transition(Status.CREATED))

        failed = Status.FAILED
        self.assertFalse(failed.transition(Status.RUNNING))
        self.assertFalse(failed.transition(Status.COMPLETED))
        self.assertFalse(failed.transition(Status.FAILED))
        self.assertFalse(failed.transition(Status.ABORTED))
        self.assertFalse(failed.transition(Status.SUSPENDED))
        self.assertFalse(failed.transition(Status.UNKNOWN))
        self.assertFalse(failed.transition(Status.PENDING))
        self.assertFalse(failed.transition(Status.CREATED))

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
        )
        status.return_value = Status.RUNNING, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.RUNNING)

    @patch("orchestrator.tasks.command_processor.delay")
    @patch("submitter.toil_submitter.ToilJobSubmitter.get_outputs")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    @patch("orchestrator.tasks.set_permission")
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
        )
        status.return_value = Status.FAILED, ""
        command_processor.return_value = True
        check_job_status(job)
        job.refresh_from_db()
        self.assertEqual(job.status, Status.FAILED)

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("orchestrator.tasks.command_processor.delay")
    def test_process_jobs(self, command_processor, add, delete):
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
        )
        add.return_value = True
        delete.return_value = True

        process_jobs()
        calls = [
            call(Command(CommandType.CHECK_STATUS_ON_LSF, str(job_pending_1.id)).to_dict()),
            call(Command(CommandType.SUBMIT, str(job_created_1.id)).to_dict()),
        ]

        command_processor.assert_has_calls(calls, any_order=True)

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.status")
    def test_check_status_command_processor(self, status, add, delete):
        def _raise_retryable_exception():
            raise Exception()

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
        )
        add.return_value = True
        delete.return_value = True
        status.side_effect = _raise_retryable_exception
        with self.assertRaises(RetryException):
            command_processor(Command(CommandType.CHECK_STATUS_ON_LSF, str(job_pending_1.id)).to_dict())

    @patch("django.core.cache.cache.delete")
    @patch("django.core.cache.cache.add")
    @patch("batch_systems.lsf_client.lsf_client.LSFClient.abort")
    def test_command_processor_abort(self, abort, add, delete):
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
        )
        add.return_value = True
        delete.return_value = True
        abort.return_value = True
        command_processor(Command(CommandType.ABORT, str(job_pending.id)).to_dict())
        job_pending.refresh_from_db()
        self.assertEqual(job_pending.status, Status.ABORTED)

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
        )
        clean_directory.return_value = True
        cleanup_folders(str(cleanup_job.id), exclude=[])
        cleanup_job.refresh_from_db()
        self.assertIsNotNone(cleanup_job.job_store_clean_up)
        self.assertIsNotNone(cleanup_job.job_store_clean_up)

    def test_get_job_info_path(self):
        with self.settings(TOIL_WORK_DIR_ROOT="/toil/work/dir/root"):
            res = get_job_info_path("job_id")
            self.assertEqual(res, "/toil/work/dir/root/job_id/.run.info")

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
                root_permission=expected_permission,
                external_id="ext_id",
                status=Status.COMPLETED,
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
                    root_permission=expected_permission,
                    external_id="ext_id",
                    status=Status.COMPLETED,
                )
                set_permission(job_completed)

    def test_permission_wrong_path(self):
        with self.assertRaises(RuntimeError):
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
                    root_dir="/awk",
                    root_permission=expected_permission,
                    external_id="ext_id",
                    status=Status.COMPLETED,
                )
                set_permission(job_completed)
