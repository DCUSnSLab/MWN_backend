def app

pipeline {
    agent {
        // k8s 환경이므로 'any' 보다는 정의된 label을 사용하는 것이 안전합니다.
        // 특정 label이 없다면 kubernetes 플러그인이 기본 제공하는 jnlp 에이전트를 사용합니다.
        kubernetes {
            label 'jenkins-agent'
        }
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Ready') {
            steps {
                echo "Ready to build"
                echo "Build Number: ${env.BUILD_NUMBER}"
                echo "Git Commit: ${env.GIT_COMMIT}"
            }
        }

        stage('Build image') {
            steps {
                script {
                    // Docker Pipeline 플러그인이 반드시 설치되어 있어야 합니다.
                    app = docker.build("harbor.cu.ac.kr/mwn/backend:${env.BUILD_NUMBER}")
                }
            }
        }

        stage('Push image') {
            steps {
                script {
                    // harbor 인증 정보(ID/PW)가 Jenkins Credentials에 'harbor'라는 ID로 등록되어 있어야 합니다.
                    docker.withRegistry("https://harbor.cu.ac.kr", "harbor") {
                        app.push("latest")
                        app.push("${env.BUILD_NUMBER}")
                    }
                }
            }
        }

        stage('Kubernetes deploy') {
            steps {
                script {
                    // SSH Steps 플러그인이 설치되어 있어야 sshCommand를 사용할 수 있습니다.
                    def remote = [:]
                    remote.name = 'deploy-server'
                    remote.host = '203.250.35.87'
                    remote.user = 'junhp1234'
                    // 보안을 위해 비밀번호는 Credentials(Store)를 사용하는 것이 좋지만, 
                    // 기존 코드 유지 보수를 위해 우선 유지합니다.
                    remote.password = 'gPdls0348!'
                    remote.allowAnyHosts = true

                    sshCommand remote: remote, command: 'kubectl apply -f /services/mwn/mwn_backend_service_loadbalancer.yaml -n mwn'
                    sshCommand remote: remote, command: 'kubectl rollout restart deployment/mwn-backend -n mwn'
                }
            }
        }

        stage('Complete') {
            steps {
                sh "echo 'The end'"
            }
        }
    }
}