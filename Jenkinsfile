pipeline {
  agent any
  parameters {
      choice(name: 'SERVER', choices: ['DEV', 'STAGE', 'PROD'], description: 'Server')
  }
  stages {
      stage('Deploy to Dev') {
      when {
        expression { params.SERVER == 'DEV' }
      }
      steps {
        echo 'deply to dev'
        sshagent(credentials: ['a4d999a5-6318-4659-83be-3f148a5490ca']) {
            sh 'ssh  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/juno/work/ci/jenkins/known_hosts voyager@silo.mskcc.org "cd /srv/services/ridgeback_dev_2/code/ridgeback && source /juno/work/ci/jenkins/lsf.sh && git pull && git checkout $BRANCH_NAME && cd /srv/services/ridgeback_dev_2 && source run_restart.sh"'
        }
      }
      }
      stage('Deploy to Stage') {
      when {
        expression { params.SERVER == 'STAGE' }
      }
      steps {
        echo 'deply to stage'
        sshagent(credentials: ['a4d999a5-6318-4659-83be-3f148a5490ca']) {
          sh 'ssh  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/juno/work/ci/jenkins/known_hosts voyager@silo.mskcc.org "cd /srv/services/staging_voyager/ridgeback/code/ridgeback && source /juno/work/ci/jenkins/lsf.sh && git pull && git checkout $BRANCH_NAME && cd ../.. && source run_restart.sh"'
        }
      }
      }
    stage('Deploy to Prod') {
          when {
          expression { params.SERVER == 'PROD' }
          }
      steps {
        echo 'deply to PROD'
        sshagent(credentials: ['a4d999a5-6318-4659-83be-3f148a5490ca']) {
          sh 'ssh  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/juno/work/ci/jenkins/known_hosts voyager@voyager.mskcc.org "cd /srv/services/ridgeback/code/ridgeback && source /juno/work/ci/jenkins/lsf.sh && git pull && git checkout $BRANCH_NAME && git pull && source run_restart.sh"'
        }
      }
    }
  }
}
