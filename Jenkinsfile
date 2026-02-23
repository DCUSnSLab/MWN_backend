pipeline {
    agent {
        kubernetes {
            yaml """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: jnlp
    image: jenkins/inbound-agent:latest
  - name: docker
    image: docker:24.0.6  # Docker 클라이언트가 포함된 이미지
    command: ['cat']
    tty: true
    volumeMounts:
    - name: docker-sock
      mountPath: /var/run/docker.sock
  volumes:
  - name: docker-sock
    hostPath:
      path: /var/run/docker.sock
"""
        }
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Build & Push image') {
            steps {
                // 'docker' 컨테이너 환경에서 실행
                container('docker') {
                    script {
                        // harbor 인증 정보를 사용 (Jenkins Credentials ID: 'harbor')
                        docker.withRegistry("https://harbor.cu.ac.kr", "harbor") {
                            def app = docker.build("harbor.cu.ac.kr/mwn/backend:${env.BUILD_NUMBER}")
                            app.push("latest")
                            app.push("${env.BUILD_NUMBER}")
                        }
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

                    sshCommand remote: remote, command: "kubectl apply -f /services/mwn/mwn_backend_service_loadbalancer.yaml -n mwn"
                    sshCommand remote: remote, command: "kubectl rollout restart deployment/mwn-backend -n mwn"
                }
            }
        }
    }
}