@description('Name of the Ollama Container App.')
param appName string

@description('Azure region.')
param location string

@description('Resource ID of the Container Apps managed environment.')
param containerAppEnvironmentId string

@description('Container image for Ollama (e.g. ollama/ollama:latest).')
param image string

@description('Optional ACR login server for registry authentication.')
param registryServer string = ''

@description('Name of the GPU workload profile defined on the managed environment.')
param workloadProfileName string

@description('Ollama models to pull on startup.')
param modelNames array = [
  'llama3.1:8b'
]

@description('Minimum replicas (0 enables scale-to-zero).')
param minReplicas int = 0

@description('Maximum replicas.')
param maxReplicas int = 1

@description('CPU cores allocated to the Ollama container.')
param cpu int = 4

@description('Memory allocated to the Ollama container (e.g. 8Gi, 16Gi).')
param memory string = '8Gi'

@description('How long Ollama keeps models loaded in memory after requests (e.g. 30m).')
param keepAlive string = '30m'

@description('Expose Ollama over external ingress. Keep false for internal-only service access.')
param ingressExternal bool = false

var startupPullModels = empty(modelNames) ? 'llama3.1:8b' : join(modelNames, ',')

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    workloadProfileName: workloadProfileName
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: ingressExternal
        targetPort: 11434
        transport: 'auto'
      }
      registries: empty(registryServer)
        ? []
        : [
            {
              server: registryServer
              identity: 'system'
            }
          ]
    }
    template: {
      containers: [
        {
          name: appName
          image: image
          command: [
            '/bin/sh'
            '-c'
            'ollama serve & pid=$!; until ollama list >/dev/null 2>&1; do sleep 2; done; for model in $(echo "$OLLAMA_PULL_MODELS" | tr "," " "); do [ -n "$model" ] && ollama pull "$model"; done; wait $pid'
          ]
          env: [
            {
              name: 'OLLAMA_HOST'
              value: '0.0.0.0:11434'
            }
            {
              name: 'OLLAMA_PULL_MODELS'
              value: startupPullModels
            }
            {
              name: 'OLLAMA_KEEP_ALIVE'
              value: keepAlive
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/api/tags'
                port: 11434
              }
              initialDelaySeconds: 10
              periodSeconds: 10
              failureThreshold: 90
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/api/tags'
                port: 11434
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/tags'
                port: 11434
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
          resources: {
            cpu: cpu
            memory: memory
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output principalId string = app.identity.principalId
