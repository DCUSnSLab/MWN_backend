/* pipeline 변수 설정 */
def app

pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Ready') {
            steps {
                echo "Ready to build"
                echo "${env.BUILD_NUMBER}"
                echo "${env.GIT_COMMIT}"
            }
        }

        stage('Build image') {
            steps {
                script {
                    app = docker.build("harbor.cu.ac.kr/mwn/backend")
                }
            }
        }

        stage('Push image') {
            steps {
                script {
                    def BUILD_NUMBER_1 = BUILD_NUMBER.toInteger()
                    docker.withRegistry("https://harbor.cu.ac.kr", "harbor") {
                        app.push("latest")
                        app.push("${BUILD_NUMBER_1}")
                    }
                }
            }
        }

        stage('Kubernetes deploy') {
            steps {
                script {
                    def remote = [:]
                    remote.name = 'deploy-server'
                    remote.host = '203.250.35.87'
                    remote.user = 'junhp1234'
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
