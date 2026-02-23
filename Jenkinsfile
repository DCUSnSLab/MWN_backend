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
      - name: harbor-auth
        mountPath: /kaniko/.docker/
  volumes:
    - name: harbor-auth
      projected:
        sources:
          - secret:
              name: harbor-registry-secret # k8s에 등록된 harbor 인증 secret 이름
              items:
                - key: .dockerconfigjson
                  path: config.json
"""
        }
    }

    environment {
        REGISTRY = "harbor.cu.ac.kr"
        IMAGE_NAME = "mwn/backend"
        TAG = "${env.BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build and Push with Kaniko') {
            steps {
                container('kaniko') {
                    script {
                        // /workspace 는 Jenkins 에이전트의 기본 소스 경로입니다.
                        sh """
                        /kaniko/executor \
                          --context=\${WORKSPACE} \
                          --dockerfile=\${WORKSPACE}/Dockerfile \
                          --destination=${REGISTRY}/${IMAGE_NAME}:${TAG} \
                          --destination=${REGISTRY}/${IMAGE_NAME}:latest
                        """
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