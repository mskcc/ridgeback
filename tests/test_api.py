from mock import patch
from uuid import uuid4
from orchestrator.models import Job
from rest_framework import status
from rest_framework.test import APITestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.timezone import now


class JobTestCase(APITestCase):
    def setUp(self):
        example_app = {
            "github": {
                "repository": "example_repository",
                "entrypoint": "example_entrypoint",
            }
        }
        self.example_job = Job.objects.create(
            type=0,
            app=example_app,
            root_dir="example_rootdir",
            id="7aacda86-b12f-4068-b2e3-a96552430a0f",
            job_store_location="/example_job_store",
        )
        self.api_root = reverse("api-root")

    def test_list(self):
        url = self.api_root + "jobs/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["id"], self.example_job.id)

    def test_read(self):
        url = "{}jobs/{}/".format(self.api_root, self.example_job.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["id"], self.example_job.id)

    def test_404_read(self):
        url = "{}jobs/{}/".format(self.api_root, self.example_job.id[::-1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("orchestrator.tasks.submit_job_to_lsf")
    def test_create(self, submit_jobs_mock):
        url = self.api_root + "jobs/"
        submit_jobs_mock.return_value = None
        data = {
            "type": 0,
            "app": self.example_job.app,
            "root_dir": self.example_job.root_dir,
            "inputs": {"example_input": True},
            "metadata": {"run_id": str(uuid4())},
            "base_dir": "/base_dir",
        }
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.json()["metadata"].get("run_id"))

    def test_create_empty(self):
        url = self.api_root + "jobs/"
        data = {}
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_unauthorized(self):
        url = "{}jobs/{}/".format(self.api_root, self.example_job.id)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_authorized(self):
        url = "{}jobs/{}/".format(self.api_root, self.example_job.id)
        admin_user = User.objects.create_superuser("admin", "sample_email", "password")
        self.client.force_authenticate(user=admin_user)
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch("orchestrator.tasks.submit_job_to_lsf")
    def test_resume(self, submit_jobs_mock):
        url = "{}jobs/{}/resume/".format(self.api_root, self.example_job.id)
        submit_jobs_mock.return_value = None
        data = {"type": 0, "root_dir": self.example_job.root_dir, "base_dir": "/base_dir"}
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.json()["resume_job_store_location"],
            self.example_job.job_store_location,
        )

    def test_resume_job_missing(self):
        url = "{}jobs/{}/resume/".format(self.api_root, self.example_job.id[::-1])
        data = {"root_dir": self.example_job.root_dir, "base_dir": "/base_dir"}
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_resume_jobstore_cleaned_up(self):
        current_job = Job.objects.get(id=self.example_job.id)
        current_job.job_store_clean_up = now()
        current_job.save()
        url = "{}jobs/{}/resume/".format(self.api_root, self.example_job.id)
        data = {"root_dir": self.example_job.root_dir, "base_dir": "/base_dir"}
        response = self.client.post(url, data=data, format="json")
        self.assertEqual(response.status_code, status.HTTP_410_GONE)
