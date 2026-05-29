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
                // withCredentials 구문을 통해 SSH 정보를 안전하게 가져옵니다.
                withCredentials([usernamePassword(credentialsId: 'junehong-deploy-server-auth', usernameVariable: 'SSH_USER', passwordVariable: 'SSH_PASS')]) {
                    script {
                        def remote = [:]
                        remote.name = 'deploy-server'
                        remote.host = '203.250.35.87'
                        remote.user = "${SSH_USER}"
                        remote.password = "${SSH_PASS}"
                        remote.allowAnyHosts = true

                        // 레포의 manifest를 deploy-server로 전송 후 적용
                        // (레포가 단일 진실 공급원 - single source of truth)
                        // /tmp/ 경유: /services/mwn/ 는 SSH 사용자에게 쓰기 권한이 없어 SFTP PUT 실패.
                        sshPut remote: remote, from: 'k8s/mwn_backend.yaml', into: '/tmp/mwn_backend.yaml'
                        // backend 이미지를 불변 빌드번호 태그로 치환 후 apply.
                        // :latest(가변) 대신 :${BUILD_NUMBER}를 박으면 apply 만으로 롤아웃이 트리거되어
                        // rollout restart 꼼수가 불필요하고, kubectl rollout undo 로 즉시 롤백이 가능하다.
                        // postgres:15-alpine 은 패턴이 달라 치환되지 않는다.
                        sshCommand remote: remote, command: "sed -i 's#harbor.cu.ac.kr/mwn/backend:latest#harbor.cu.ac.kr/mwn/backend:${env.BUILD_NUMBER}#g' /tmp/mwn_backend.yaml"
                        sshCommand remote: remote, command: "kubectl apply -f /tmp/mwn_backend.yaml -n mwn"
                        sshCommand remote: remote, command: "rm -f /tmp/mwn_backend.yaml"
                    }
                }
            }
        }
    }
}