import os
from django.apps import apps
from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from toil_orchestrator import migrations
from django_test_migrations.contrib.unittest_case import MigratorTestCase
from toil_orchestrator.models import Status
import json

current_app = 'toil_orchestrator'

class TestMigration(MigratorTestCase):

    def setUp(self,migrate_from,migrate_to):
        self.migrate_from = (current_app, self.get_migration_file_name(migrate_from))
        self.migrate_to = (current_app, self.get_migration_file_name(migrate_to))
        super().setUp()

    def get_migration_file_name(self,number):
        migration_path = migrations.__path__[0]
        migration_files = os.listdir(migration_path)
        for single_file in migration_files:
            single_file_split = single_file.split('_')
            if str(number) in single_file_split[0]:
                return os.path.splitext(single_file)[0]

class TestMessageMigration(TestMigration):

    def setUp(self):
        super().setUp(13,17)

    def prepare(self):
        job =  self.old_state.apps.get_model('toil_orchestrator','job')
        job.objects.create(
            app={
                    "github": {
                    "entrypoint": "tempo.cwl",
                    "repository": "https://github.com/mskcc-cwl/tempo"
                    }
                },
            message="sample_info_string"

            )

    def test_migration(self):
        job =  self.new_state.apps.get_model('toil_orchestrator','job')
        current_job = job.objects.all().first()

    def test_message(self):
        job =  self.new_state.apps.get_model('toil_orchestrator','job')
        current_job = job.objects.all().first()
        new_message_obj = json.loads(current_job.message)
        self.assertEqual(new_message_obj['info'],"sample_info_string")

class TestDateMigration(TestMigration):

    def setUp(self):
        super().setUp(12,13)

    def prepare(self):
        job =  self.old_state.apps.get_model('toil_orchestrator','job')
        job.objects.create(
            app={
                    "github": {
                    "entrypoint": "tempo.cwl",
                    "repository": "https://github.com/mskcc-cwl/tempo"
                    }
                },
            status=Status.COMPLETED,
            finished=None,
            started=None,
            submitted=None
            )

    def test_date_change(self):
        job =  self.new_state.apps.get_model('toil_orchestrator','job')
        current_job = job.objects.all().first()
        self.assertNotEqual(current_job.started,None)
        self.assertNotEqual(current_job.submitted,None)
        self.assertNotEqual(current_job.finished,None)

