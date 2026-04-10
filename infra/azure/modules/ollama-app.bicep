@description('Name of the Ollama Container App.')
param appName string

@description('Azure region.')
param location string

@description('Resource ID of the Container Apps managed environment.')
param containerAppEnvironmentId string

@description('Container image for Ollama (e.g. ollama/ollama:latest).')
param image string

@description('ACR login server for registry authentication.')
param registryServer string

@description('Name of the GPU workload profile defined on the managed environment.')
param workloadProfileName string

@description('Ollama model to pull on startup (e.g. llama3.1:8b).')
param modelName string = 'llama3.1:8b'

@description('Minimum replicas (0 enables scale-to-zero).')
param minReplicas int = 0

@description('Maximum replicas.')
param maxReplicas int = 1

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    workloadProfileName: workloadProfileName
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 11434
        transport: 'auto'
      }
      registries: [
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
            'ollama serve & sleep 5 && ollama pull ${modelName} && wait'
          ]
          env: [
            {
              name: 'OLLAMA_HOST'
              value: '0.0.0.0:11434'
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
              failureThreshold: 30
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
            cpu: 4
            memory: '8Gi'
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
