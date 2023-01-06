from django.test import TestCase
from orchestrator.scheduler import Scheduler
from orchestrator.models import Job, Status, PipelineType


class SchedulerTest(TestCase):
    def create_jobs(self, status, count, walltime):
        for i in range(count):
            Job.objects.create(
                type=PipelineType.CWL,
                app={"github": "link"},
                root_dir="root_dir",
                job_store_location="job_store_location",
                status=status,
                walltime=walltime,
            )

    def test_full_cluster(self):
        self.create_jobs(Status.RUNNING, 150, 10000)  # Long Jobs
        self.create_jobs(Status.RUNNING, 100, 6000)  # Medium Jobs
        self.create_jobs(Status.RUNNING, 50, 3000)  # Short Jobs
        self.create_jobs(Status.CREATED, 2, 10200)  # Long Jobs Pending
        self.create_jobs(Status.CREATED, 2, 5500)  # Medium Jobs Pending
        self.create_jobs(Status.CREATED, 2, 2000)  # Short Jobs Pending
        jobs = Scheduler.get_jobs_to_submit()
        self.assertEqual(len(jobs), 0)

    def test_long_jobs_full(self):
        self.create_jobs(Status.RUNNING, 150, 10000)  # Long Jobs
        self.create_jobs(Status.RUNNING, 80, 6000)  # Medium Jobs
        self.create_jobs(Status.RUNNING, 20, 3000)  # Short Jobs
        self.create_jobs(Status.CREATED, 2, 10200)  # Long Jobs Pending
        self.create_jobs(Status.CREATED, 2, 5500)  # Medium Jobs Pending
        self.create_jobs(Status.CREATED, 2, 2000)  # Short Jobs Pending
        jobs = Scheduler.get_jobs_to_submit()
        self.assertEqual(len(jobs), 4)
        for job in jobs:
            self.assertTrue(job.walltime in (5500, 2000))
            self.assertEqual(job.status, Status.CREATED)

    def test_partial(self):
        self.create_jobs(Status.RUNNING, 150, 10000)  # Long Jobs
        self.create_jobs(Status.RUNNING, 80, 6000)  # Medium Jobs
        self.create_jobs(Status.RUNNING, 20, 3000)  # Short Jobs
        self.create_jobs(Status.CREATED, 2, 5500)  # Medium Jobs Pending
        self.create_jobs(Status.CREATED, 40, 2000)  # Short Jobs Pending
        jobs = Scheduler.get_jobs_to_submit()
        self.assertEqual(len(jobs), 32)
        for job in jobs:
            self.assertTrue(job.walltime in (5500, 2000))
            self.assertEqual(job.status, Status.CREATED)
