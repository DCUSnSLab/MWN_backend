pipeline {
    agent {
        kubernetes {
            yaml """
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: kaniko
    image: gcr.io/kaniko-project/executor:debug
    command: ['sleep']
    args: ['99d']
    volumeMounts:
      - name: kaniko-config
        mountPath: /kaniko/.docker/
  volumes:
    - name: kaniko-config
      emptyDir: {}
"""
        }
    }

    stages {
        stage('Build and Push') {
            steps {
                container('kaniko') {
                    // 기존 Jenkins에 등록된 'harbor' Credentials(ID/PW 방식)를 사용
                    withCredentials([usernamePassword(credentialsId: 'harbor', usernameVariable: 'USER', passwordVariable: 'PASS')]) {
                        script {
                            // 1. Kaniko가 인식할 수 있는 auth 정보(base64)를 생성하여 config.json에 기록
                            def auth = "${USER}:${PASS}".bytes.encodeBase64().toString()
                            sh """
                            echo '{"auths": {"harbor.cu.ac.kr": {"auth": "${auth}"}}}' > /kaniko/.docker/config.json
                            """
                            
                            // 2. 빌드 및 푸시 진행
                            sh """
                            /kaniko/executor \
                              --context=${WORKSPACE} \
                              --dockerfile=${WORKSPACE}/Dockerfile \
                              --destination=harbor.cu.ac.kr/mwn/backend:${env.BUILD_NUMBER} \
                              --destination=harbor.cu.ac.kr/mwn/backend:latest
                            """
                        }
                    }
                }
            }
        }

        stage('Kubernetes deploy') {
            steps {
                script {
                    // SSH Steps 플러그인 필요
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