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
    image: docker:24.0.6
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
        stage('Build & Push image') {
            steps {
                container('docker') {
                    script {
                        // 'harbor-auth'라는 ID의 Credentials를 사용합니다.
                        docker.withRegistry("https://harbor.cu.ac.kr", "harbor-auth") {
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
                // withCredentials 구문을 통해 SSH 정보를 안전하게 가져옵니다.
                withCredentials([usernamePassword(credentialsId: 'junehong-deploy-server-auth', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')]) {
                    script {
                        def remote = [:]
                        remote.name = 'deploy-server'
                        remote.host = '203.250.35.87'
                        remote.user = "${SSH_USER}"
                        remote.password = "${SSH_PASS}"
                        remote.allowAnyHosts = true

                        sshCommand remote: remote, command: "kubectl apply -f /services/mwn/mwn_backend_service_loadbalancer.yaml -n mwn"
                        sshCommand remote: remote, command: "kubectl rollout restart deployment/mwn-backend -n mwn"
                    }
                }
            }
        }
    }
}