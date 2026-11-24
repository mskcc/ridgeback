import os
import shutil
import tempfile
from mock import patch, PropertyMock
from django.test import TestCase
from orchestrator.models import Job, Status, PipelineType
from submitter.nextflow_submitter import NextflowJobSubmitter


class TestNextflowSubmitter(TestCase):
    def setUp(self):
        self.job = Job.objects.create(
            type=PipelineType.NEXTFLOW,
            app={
                "github": {
                    "version": "feature/voyager",
                    "entrypoint": "dsl2.nf",
                    "repository": "git@github.com:sivkovic/tempo.git",
                }
            },
            output_directory="/tempo/Results",
            base_dir="/tempo",
            root_dir="/tempo/Results",
            status=Status.CREATED,
            inputs={
                "config": 'executor {\r\n  name = "lsf"\r\n  queueSize = 5000000000\r\n  perJobMemLimit = true\r\n}'
                '\r\n\r\nprocess {\r\n  memory = "8.GB"\r\n   time = { task.attempt < 3 ? 3.h * '
                'task.attempt  : 500.h }\r\n  clusterOptions = ""\r\n  scratch = true\r\n  beforeScript = '
                '". /etc/profile.d/modules.sh; module load singularity/3.1.1; unset R_LIBS; catch_term () '
                "{ echo 'caught USR2/TERM signal'; set +e; false; on_exit ; } ; trap catch_term USR2 TERM\""
                "\r\n}\r\n\r\nprocess.input.mode = 'copy'\r\n\r\nparams {\r\n  publishDirMode = \"copy\"\r"
                '\n  outname="/juno/work/tempo/beagle_test/chronos/09625_P/0.1.0/20231027_02_31_801438/json'
                '/Tempo/feature/voyager/bamMapping.tsv" \r\n  outDir = "${PWD}" \r\n  max_memory = "'
                '128.GB"\r\n  mem_per_core = true\r\n  reference_base = "/juno/work/taylorlab/cmopipeline'
                '" \r\n  targets_base   = "${reference_base}/mskcc-igenomes/${params.genome.toLowerCase()}'
                "/tempo_targets\"\r\n  genome_base = params.genome == 'GRCh37' ? \"${reference_base}/"
                "mskcc-igenomes/igenomes/Homo_sapiens/GATK/GRCh37\" : params.genome == 'GRCh38' ? \""
                '${reference_base}/mskcc-igenomes/igenomes/Homo_sapiens/GATK/GRCh38" : "${reference_base}'
                '/mskcc-igenomes/igenomes/smallGRCh37"\r\n  minWallTime = 3.h\r\n  medWallTime = 6.h\r\n  '
                "maxWallTime = 500.h\r\n  wallTimeExitCode = '140,0,1,143'\r\n}\r\n\r\nenv {\r\n  "
                "SPARK_LOCAL_DIRS = './'\r\n}\r\n\r\ntrace {\r\n    enabled = true\r\n    file = \""
                "/juno/work/tempo/beagle_test/chronos/09625_P/0.1.0/20231027_02_31_801438/json/Tempo"
                '/feature/voyager/trace.txt"\r\n}',
                "inputs": [
                    {
                        "name": "mapping",
                        "content": "SAMPLE\tTARGET\tFASTQ_PE1\tFASTQ_PE2\tNUM_OF_PAIRS\ns_C_RP3UAF_P002_d\tidt\t"
                        "/juno/archive/msk/cmo/FASTQ/PITT_0481_AHHWKMBBXY/Project_09625_P/"
                        "Sample_P-0024205-T02-WES_inv_IGO_09625_P_1/"
                        "P-0024205-T02-WES_inv_IGO_09625_P_1_S60_R1_001.fastq.gz\t/juno/archive/msk/"
                        "cmo/FASTQ/PITT_0481_AHHWKMBBXY/Project_09625_P/"
                        "Sample_P-0024205-T02-WES_inv_IGO_09625_P_1/"
                        "P-0024205-T02-WES_inv_IGO_09625_P_1_S60_R2_001.fastq.gz\t1\n",
                    }
                ],
                "params": {
                    "genome": "GRCh37",
                    "somatic": None,
                    "aggregate": None,
                    "assayType": "exome",
                    "workflows": "qc",
                    "params.outname": None,
                },
                "outputs": [
                    {
                        "path": "/juno/outputs/Tempo/feature/voyager/bamMapping.tsv",
                        "template": "SAMPLE:string\tTARGET:string\tBAM:File\tBAI:File",
                    }
                ],
                "profile": "juno",
            },
        )

    def test_get_outputs(self):
        submitter = NextflowJobSubmitter(
            str(self.job.id),
            self.job.app,
            self.job.inputs,
            self.job.root_dir,
            self.job.resume_job_store_location,
            log_dir=self.job.log_dir,
            memlimit=None,
            walltime=None,
            tool_walltime=None,
        )
        submitter.get_outputs()

    def _submitter(self, inputs=None):
        submitter = NextflowJobSubmitter(
            str(self.job.id),
            self.job.app,
            inputs if inputs is not None else self.job.inputs,
            self.job.root_dir,
            self.job.resume_job_store_location,
            log_dir=self.job.log_dir,
            memlimit=None,
            walltime=None,
            tool_walltime=None,
        )
        submitter.job_work_dir = self.work_dir
        submitter.job_outputs_dir = self.outputs_dir
        return submitter

    def _setup_dirs(self):
        self.work_dir = tempfile.mkdtemp()
        self.outputs_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.work_dir)
        self.addCleanup(shutil.rmtree, self.outputs_dir)

    def _write_output(self, rel):
        full = os.path.join(self.outputs_dir, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write("data")
        return full

    def _write_published_manifest(self, name, relative_paths):
        rows = ["run_name\tnextflow_version\toutdir\tpublish_dir\trelative_path\tfull_path\tsize_bytes"]
        for rel in relative_paths:
            full = self._write_output(rel)
            rows.append("\t".join(["run", "25.10.4", self.outputs_dir, os.path.dirname(full), rel, full, "4"]))
        path = os.path.join(self.outputs_dir, name)
        with open(path, "w") as f:
            f.write("\n".join(rows) + "\n")
        return path

    def _locations(self, outputs):
        return sorted(o["location"] for o in outputs["outputs"])

    def _expected(self, relative_paths):
        return sorted("file://" + os.path.join(self.outputs_dir, p) for p in relative_paths)

    def test_dump_published_manifest_config(self):
        self._setup_dirs()
        submitter = self._submitter()
        submitter._dump_app_inputs()
        self.assertTrue(os.path.exists(submitter.published_manifest_config_location))
        with open(submitter.published_manifest_config_location) as f:
            self.assertIn("workflow.onComplete", f.read())

    def test_dump_published_manifest_config_without_job_config(self):
        self._setup_dirs()
        inputs = dict(self.job.inputs)
        inputs.pop("config")
        submitter = self._submitter(inputs)
        submitter._dump_app_inputs()
        self.assertTrue(os.path.exists(submitter.published_manifest_config_location))

    @patch.object(NextflowJobSubmitter, "app_location", new_callable=PropertyMock, return_value="/app/main.nf")
    def test_command_line_attaches_published_manifest_config_before_job_config(self, _):
        self._setup_dirs()
        submitter = self._submitter()
        submitter._dump_app_inputs()
        command_line = submitter._command_line()
        manifest_idx = command_line.index(submitter.published_manifest_config_location)
        job_config_idx = command_line.index(submitter.config_location)
        self.assertEqual(command_line[manifest_idx - 1], "-c")
        self.assertLess(manifest_idx, job_config_idx)

    @patch.object(NextflowJobSubmitter, "app_location", new_callable=PropertyMock, return_value="/app/main.nf")
    def test_command_line_without_published_manifest_config(self, _):
        # Jobs prepared before this change have no copy in the work dir
        self._setup_dirs()
        submitter = self._submitter()
        self.assertNotIn(submitter.published_manifest_config_location, submitter._command_line())

    @patch.object(NextflowJobSubmitter, "app_location", new_callable=PropertyMock, return_value="/app/main.nf")
    def test_submit_command_sets_manifest_dir(self, _):
        self._setup_dirs()
        submitter = self._submitter()
        _, _, _, _, _, env = submitter.get_submit_command()
        self.assertEqual(env["NXF_MANIFEST_DIR"], self.outputs_dir)

    def test_get_outputs_tempo_from_published_manifest(self):
        # Tempo job inputs (with "outputs") are parsed from the manifest like any other job
        self._setup_dirs()
        self._write_published_manifest("published_manifest_run.tsv", ["bams/s1.bam", "bams/s1.bai"])
        outputs, error_message = self._submitter().get_outputs()
        self.assertIsNone(error_message)
        self.assertEqual(self._locations(outputs), self._expected(["bams/s1.bam", "bams/s1.bai"]))
        self.assertEqual(outputs["outputs"][0]["size"], 4)

    def test_get_outputs_uses_newest_published_manifest(self):
        self._setup_dirs()
        self._write_published_manifest("published_manifest_old_run.tsv", ["old/a.txt"])
        newest = self._write_published_manifest("published_manifest_new_run.tsv", ["foo/a.txt", "bar/b/c.tsv"])
        mtime = os.path.getmtime(newest) + 10
        os.utime(newest, (mtime, mtime))
        outputs, error_message = self._submitter().get_outputs()
        self.assertIsNone(error_message)
        self.assertEqual(self._locations(outputs), self._expected(["foo/a.txt", "bar/b/c.tsv"]))

    def test_get_outputs_bad_published_manifest(self):
        self._setup_dirs()
        with open(os.path.join(self.outputs_dir, "published_manifest_run.tsv"), "w") as f:
            f.write("not\ta\tmanifest\n1\t2\t3\n")
        outputs, error_message = self._submitter().get_outputs()
        self.assertEqual(outputs["outputs"], [])
        self.assertIn("Could not parse", error_message)

    def test_get_outputs_without_published_manifest(self):
        self._setup_dirs()
        inputs = dict(self.job.inputs)
        inputs.pop("outputs")
        outputs, error_message = self._submitter(inputs).get_outputs()
        self.assertEqual(outputs["outputs"], [])
        self.assertIn("Could not find published_manifest_*.tsv", error_message)
