targetScope = 'resourceGroup'

@description('Azure location for all resources.')
param location string = resourceGroup().location

@description('Log Analytics workspace used by the Container Apps environment.')
param logAnalyticsWorkspaceName string = 'travel-tom-llm-law'

@description('Name of the Container Apps managed environment.')
param containerEnvironmentName string = 'travel-tom-llm-cae'

@description('Name of the Ollama Container App.')
param ollamaAppName string = 'travel-tom-ollama'

@description('Container image for Ollama (e.g. ollama/ollama:latest).')
param ollamaImage string = 'ollama/ollama:latest'

@description('Comma-separated model names to pull during startup (for example: llama3.1:8b,qwen2.5:14b).')
param ollamaModelsCsv string = 'llama3.1:8b'

@description('Managed environment workload profile name assigned to the Ollama app.')
param ollamaWorkloadProfileName string = 'Consumption'

@allowed([
  'Consumption'
  'Consumption-GPU-T4'
])
@description('Workload profile type for Ollama. Use Consumption-GPU-T4 only in regions that support it.')
param ollamaWorkloadProfileType string = 'Consumption'

@minValue(0)
@description('Minimum Ollama replicas. Use 1 to avoid cold starts.')
param ollamaMinReplicas int = 1

@minValue(1)
@description('Maximum Ollama replicas.')
param ollamaMaxReplicas int = 1

@minValue(1)
@description('CPU cores for the Ollama container.')
param ollamaCpu int = 4

@description('Memory for the Ollama container (for example 8Gi, 16Gi, 32Gi).')
param ollamaMemory string = '8Gi'

@description('How long Ollama keeps models in memory after requests.')
param ollamaKeepAlive string = '30m'

@description('Expose Ollama publicly. Keep false when only internal services should access it.')
param ollamaIngressExternal bool = false

var ollamaModels = split(ollamaModelsCsv, ',')

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: ollamaWorkloadProfileName
        workloadProfileType: ollamaWorkloadProfileType
      }
    ]
  }
}

module ollamaApp './modules/ollama-app.bicep' = {
  name: 'ollama-service-app'
  params: {
    appName: ollamaAppName
    location: location
    containerAppEnvironmentId: containerEnv.id
    image: ollamaImage
    workloadProfileName: ollamaWorkloadProfileName
    modelNames: ollamaModels
    minReplicas: ollamaMinReplicas
    maxReplicas: ollamaMaxReplicas
    cpu: ollamaCpu
    memory: ollamaMemory
    keepAlive: ollamaKeepAlive
    ingressExternal: ollamaIngressExternal
  }
}

output ollamaAppResourceName string = ollamaAppName
output ollamaFqdn string = ollamaApp.outputs.fqdn
output containerEnvironmentResourceName string = containerEnvironmentName
output logAnalyticsWorkspaceResourceName string = logAnalyticsWorkspaceName
