from django.test import TestCase
from mock import patch, Mock
from django.conf import settings
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
                        "repository": "git@github.com:sivkovic/tempo.git"
                    }
                },
            output_directory="/tempo/Results",
            base_dir="/tempo",
            root_dir="/tempo/Results",
            status=Status.CREATED,
            inputs={
                "config": "executor {\r\n  name = \"lsf\"\r\n  queueSize = 5000000000\r\n  perJobMemLimit = true\r\n}\r\n\r\nprocess {\r\n  memory = \"8.GB\"\r\n   time = { task.attempt < 3 ? 3.h * task.attempt  : 500.h }\r\n  clusterOptions = \"\"\r\n  scratch = true\r\n  beforeScript = \". /etc/profile.d/modules.sh; module load singularity/3.1.1; unset R_LIBS; catch_term () { echo 'caught USR2/TERM signal'; set +e; false; on_exit ; } ; trap catch_term USR2 TERM\"\r\n}\r\n\r\nprocess.input.mode = 'copy'\r\n\r\nparams {\r\n  publishDirMode = \"copy\"\r\n  outname=\"/juno/work/tempo/beagle_test/chronos/09625_P/0.1.0/20231027_02_31_801438/json/Tempo/feature/voyager/bamMapping.tsv\" \r\n  outDir = \"${PWD}\" \r\n  max_memory = \"128.GB\"\r\n  mem_per_core = true\r\n  reference_base = \"/juno/work/taylorlab/cmopipeline\" \r\n  targets_base   = \"${reference_base}/mskcc-igenomes/${params.genome.toLowerCase()}/tempo_targets\"\r\n  genome_base = params.genome == 'GRCh37' ? \"${reference_base}/mskcc-igenomes/igenomes/Homo_sapiens/GATK/GRCh37\" : params.genome == 'GRCh38' ? \"${reference_base}/mskcc-igenomes/igenomes/Homo_sapiens/GATK/GRCh38\" : \"${reference_base}/mskcc-igenomes/igenomes/smallGRCh37\"\r\n  minWallTime = 3.h\r\n  medWallTime = 6.h\r\n  maxWallTime = 500.h\r\n  wallTimeExitCode = '140,0,1,143'\r\n}\r\n\r\nenv {\r\n  SPARK_LOCAL_DIRS = './'\r\n}\r\n\r\ntrace {\r\n    enabled = true\r\n    file = \"/juno/work/tempo/beagle_test/chronos/09625_P/0.1.0/20231027_02_31_801438/json/Tempo/feature/voyager/trace.txt\"\r\n}",
                "inputs": [{"name": "mapping",
                            "content": "SAMPLE\tTARGET\tFASTQ_PE1\tFASTQ_PE2\tNUM_OF_PAIRS\ns_C_RP3UAF_P002_d\tidt\t/juno/archive/msk/cmo/FASTQ/PITT_0481_AHHWKMBBXY/Project_09625_P/Sample_P-0024205-T02-WES_inv_IGO_09625_P_1/P-0024205-T02-WES_inv_IGO_09625_P_1_S60_R1_001.fastq.gz\t/juno/archive/msk/cmo/FASTQ/PITT_0481_AHHWKMBBXY/Project_09625_P/Sample_P-0024205-T02-WES_inv_IGO_09625_P_1/P-0024205-T02-WES_inv_IGO_09625_P_1_S60_R2_001.fastq.gz\t1\n"}],
                "params": {"genome": "GRCh37",
                           "somatic": None,
                           "aggregate": None,
                           "assayType": "exome",
                           "workflows": "qc",
                           "params.outname": None},
                "outputs": [
                    {"path": "/juno/outputs/Tempo/feature/voyager/bamMapping.tsv",
                     "template": "SAMPLE:string\tTARGET:string\tBAM:File\tBAI:File"}
                ],
                "profile": "juno"
            },
        )

    def test_get_outputs(self):
        submitter = NextflowJobSubmitter(str(self.job.id),
                                         self.job.app,
                                         self.job.inputs,
                                         self.job.root_dir,
                                         self.job.resume_job_store_location,
                                         log_dir=self.job.log_dir,
                                         memlimit=None,
                                         walltime=None)
        submitter.get_outputs()
