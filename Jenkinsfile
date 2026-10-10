// Multibranch Pipeline: Jenkins creates a job per branch / PR.
// push feature/*  -> (branch build) auto-create PR into main
// PR builds       -> validate WHOLE repo -> tests for changed features -> comment on PR -> merge to main
// main build      -> full regression
pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 45, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '30'))
        disableConcurrentBuilds(abortPrevious: true)
    }

    environment {
        VENV     = "${WORKSPACE}/.venv"
        BASE_URL = credentials('e2e-base-url')          // Jenkins "Secret text" credential
        // ---- PR auto-merge settings ----
        AUTO_MERGE       = 'true'      // false = validate only, never merge
        MERGE_METHOD     = 'squash'    // merge | squash | rebase
        REQUIRE_APPROVAL = 'false'     // 'true' = merge only after a reviewer approved (not fully automatic)
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install --quiet --upgrade pip
                    pip install --quiet -r requirements.txt
                '''
            }
        }

        // Developer only pushes feature/*; Jenkins opens the PR, which triggers the PR build below.
        stage('Auto-create PR') {
            when {
                allOf {
                    not { changeRequest() }
                    anyOf {
                        branch 'feature/*'
                        branch 'bugfix/*'
                        branch 'hotfix/*'
                        branch 'chore/*'
                    }
                }
            }
            steps {
                withCredentials([string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')]) {
                    sh '''
                        TITLE=$(git log -1 --pretty=%s)
                        BODY=$(printf 'Auto-created by Jenkins for branch `%s`.\n\nCommits:\n%s' "$BRANCH_NAME" "$(git log origin/main..HEAD --pretty='- %s' 2>/dev/null || git log -5 --pretty='- %s')")
                        python3 scripts/github_pr.py create-pr --head "$BRANCH_NAME" --base main --title "$TITLE" --body "$BODY"
                    '''
                }
            }
        }

        stage('PR Validation (whole repo)') {
            when { changeRequest() }
            steps {
                sh '''
                    . "$VENV/bin/activate"
                    git fetch origin "${CHANGE_TARGET}:refs/remotes/origin/${CHANGE_TARGET}"
                    TARGET_BRANCH="origin/${CHANGE_TARGET}" \
                    PR_NUMBER="${CHANGE_ID}" \
                    PR_TITLE="${CHANGE_TITLE}" \
                    PR_BRANCH="${CHANGE_BRANCH}" \
                    PR_ID="${CHANGE_ID}" \
                    PR_URL="${CHANGE_URL}" \
                    bash scripts/validate_pr.sh
                '''
            }
        }

        stage('Tests - Changed Features (PR)') {
            when { changeRequest() }
            steps {
                sh '''
                    . "$VENV/bin/activate"
                    FEATURES=$(python scripts/changed_features.py --base "origin/${CHANGE_TARGET}")
                    echo "Changed features: ${FEATURES:-none}"
                    if [ -z "$FEATURES" ]; then
                        echo "No feature changes - running smoke only"
                        pytest -m smoke --junitxml=reports/junit.xml --html=reports/report.html --self-contained-html
                    else
                        PATHS=""
                        for f in $FEATURES; do PATHS="$PATHS features/$f"; done
                        pytest $PATHS --junitxml=reports/junit.xml --html=reports/report.html --self-contained-html
                    fi
                '''
            }
        }

        stage('Merge PR to main') {
            when {
                changeRequest target: 'main'
                expression { env.AUTO_MERGE == 'true' }
            }
            steps {
                withCredentials([string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')]) {
                    script {
                        // everything above passed -> tell the PR, then merge
                        def rc = sh(returnStatus: true, script: '''
                            . "$VENV/bin/activate"
                            export PR_ID="${CHANGE_ID}"
                            python scripts/github_pr.py comment
                            python scripts/github_pr.py merge
                        ''')
                        if (rc == 10) {
                            unstable('Validation passed, PR NOT merged (needs approval / is draft)')
                        } else if (rc != 0) {
                            error('Merge failed - see log')
                        }
                    }
                }
            }
        }

        stage('Tests - Full Regression') {
            when { branch 'main' }
            steps {
                sh '''
                    . "$VENV/bin/activate"
                    pytest -n 4 --junitxml=reports/junit.xml --html=reports/report.html --self-contained-html
                '''
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
        }
        failure {
            echo 'Build failed - check the PR Validation / test stage logs.'
            script {
                if (env.CHANGE_ID) {
                    withCredentials([string(credentialsId: 'github-token', variable: 'GITHUB_TOKEN')]) {
                        sh '''
                            . "$VENV/bin/activate" || true
                            export PR_ID="${CHANGE_ID}"
                            python scripts/github_pr.py comment --body "$(cat reports/pr_validation.md 2>/dev/null || echo "❌ Build failed: ${BUILD_URL}console")" || true
                        '''
                    }
                }
            }
        }
        cleanup { cleanWs() }
    }
}
