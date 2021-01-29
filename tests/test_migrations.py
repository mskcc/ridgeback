import os
import json
from orchestrator import migrations
from django_test_migrations.contrib.unittest_case import MigratorTestCase
from orchestrator.models import Status
from unittest import skip


current_app = 'orchestrator'


class TestMigration(MigratorTestCase):

    def setUp(self, migrate_from, migrate_to):
        self.migrate_from = (current_app, self.get_migration_file_name(migrate_from))
        self.migrate_to = (current_app, self.get_migration_file_name(migrate_to))
        super().setUp()

    def get_migration_file_name(self, number):
        migration_path = migrations.__path__[0]
        migration_files = os.listdir(migration_path)
        for single_file in migration_files:
            single_file_split = single_file.split('_')
            if str(number) in single_file_split[0]:
                return os.path.splitext(single_file)[0]


class TestMessageMigration(TestMigration):

    def setUp(self):
        super().setUp(13, 18)

    def prepare(self):
        Job = self.old_state.apps.get_model('orchestrator', 'Job')
        Job.objects.create(
            type=0,
            app={
                "github": {
                    "entrypoint": "tempo.cwl",
                    "repository": "https://github.com/mskcc-cwl/tempo"
                }
            },
            message="sample_info_string"
        )

    def test_migration(self):
        Job = self.new_state.apps.get_model('orchestrator', 'Job')
        current_job = Job.objects.first()

    @skip("Debug")
    def test_message(self):
        Job = self.new_state.apps.get_model('orchestrator', 'Job')
        current_job = Job.objects.first()
        new_message_obj = json.loads(current_job.message)
        self.assertEqual(new_message_obj['info'], "sample_info_string")


class TestDateMigration(TestMigration):

    def setUp(self):
        super().setUp(12, 13)

    def prepare(self):
        Job = self.old_state.apps.get_model('orchestrator', 'Job')
        Job.objects.create(
            # type=0,
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

    @skip("Debug")
    def test_date_change(self):
        Job = self.new_state.apps.get_model('orchestrator', 'Job')
        current_job = Job.objects.first()
        self.assertNotEqual(current_job.started, None)
        self.assertNotEqual(current_job.submitted, None)
        self.assertNotEqual(current_job.finished, None)
