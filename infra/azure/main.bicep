targetScope = 'resourceGroup'

@description('Deployment environment name.')
@allowed([
  'dev'
  'prod'
])
param environment string

@description('Azure location for all resources.')
param location string = resourceGroup().location

@description('Base prefix for generated Azure resources.')
param prefix string = 'traveltom'

@description('Container image for the API app.')
param apiImage string

@description('Container image for the web app.')
param webImage string

@description('Container image for Ollama (e.g. ollama/ollama:latest).')
param ollamaImage string

@description('Ollama planning model name.')
param ollamaPlanningModel string = 'llama3.1:8b'

@description('Ollama response model name.')
param ollamaResponseModel string = 'llama3.1:8b'

@minValue(0)
@description('Minimum Ollama replicas to keep warm.')
param ollamaMinReplicas int = environment == 'prod' ? 1 : 0

@minValue(1)
@description('Maximum Ollama replicas.')
param ollamaMaxReplicas int = 1

@minValue(1)
@description('CPU cores for the Ollama container.')
param ollamaCpu int = 4

@description('Memory for the Ollama container (e.g. 8Gi, 16Gi).')
param ollamaMemory string = environment == 'prod' ? '16Gi' : '8Gi'

@description('How long Ollama keeps models in memory after requests.')
param ollamaKeepAlive string = environment == 'prod' ? '30m' : '10m'

@description('PostgreSQL admin username.')
param postgresAdminLogin string

@secure()
@description('PostgreSQL admin password.')
param postgresAdminPassword string

@description('Allowed frontend origins for API CORS.')
param corsAllowedOrigins string

@description('Optional Azure OpenAI compatible base URL.')
param openaiBaseUrl string = 'https://api.openai.com/v1'

@secure()
@description('Optional OpenAI API key.')
param openaiApiKey string = ''

@description('Optional local auth token secret for current auth flow.')
param localAuthTokenSecret string = ''

@description('Frontend API base URL injected at build/deploy time.')
param frontendApiBaseUrl string

@description('Optional Application Insights connection string for frontend telemetry.')
param frontendAppInsightsConnectionString string = ''

@description('Enable Azure MLOps foundation resources for the environment.')
param enableMlops bool = false

@description('Name of the blob container that stores dataset snapshots.')
param mlopsDatasetContainerName string = 'ml-datasets'

@description('Name of the blob container that stores trained model artifacts.')
param mlopsArtifactContainerName string = 'ml-artifacts'

@description('Name of the blob container that stores training and promotion manifests.')
param mlopsManifestContainerName string = 'ml-manifests'

@description('Name of the blob container that stores evaluation reports.')
param mlopsEvaluationContainerName string = 'ml-evaluations'

@description('Promoted ranker artifact reference for the current environment.')
param promotedMlModelArtifactUri string = ''

@description('Promoted ranker model version label for the current environment.')
param promotedMlModelVersion string = ''

var resourceToken = toLower(uniqueString(resourceGroup().id, environment))
var resourcePrefix = '${prefix}-${environment}'
var acrName = take(replace('${prefix}${environment}${resourceToken}', '-', ''), 50)
var lawName = '${resourcePrefix}-law'
var appInsightsName = '${resourcePrefix}-appi'
var keyVaultName = take(replace('${resourcePrefix}-kv-${resourceToken}', '-', ''), 24)
var storageAccountName = take(replace('${prefix}${environment}st${resourceToken}', '-', ''), 24)
var postgresServerName = '${resourcePrefix}-psql'
var postgresDatabaseName = 'traveltom'
var containerEnvName = '${resourcePrefix}-cae'
var apiAppName = '${resourcePrefix}-api'
var webAppName = '${resourcePrefix}-web'
var ollamaAppName = '${resourcePrefix}-ollama'
var mlopsStorageAccountName = take(replace('${prefix}${environment}ml${resourceToken}', '-', ''), 24)
var mlopsIdentityName = '${resourcePrefix}-mlops-id'
var mlWorkspaceName = '${resourcePrefix}-mlw'
var gpuWorkloadProfileName = 'gpu-t4'
var acrPullRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7f951dda-4ed3-4680-a7ca-43fe172d538d'
)
var storageBlobDataContributorRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)
var storageBlobDataReaderRoleDefinitionId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
)

module monitoring './modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    logAnalyticsWorkspaceName: lawName
    appInsightsName: appInsightsName
  }
}

module acr './modules/acr.bicep' = {
  name: 'acr'
  params: {
    acrName: acrName
    location: location
  }
}

module keyVault './modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    keyVaultName: keyVaultName
    location: location
    secrets: {
      OPENAI_API_KEY: openaiApiKey
      LOCAL_AUTH_TOKEN_SECRET: localAuthTokenSecret
      POSTGRES_ADMIN_PASSWORD: postgresAdminPassword
    }
  }
}

module postgres './modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    serverName: postgresServerName
    location: location
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
    databaseName: postgresDatabaseName
    environment: environment
  }
}

module mlopsStorage './modules/storage-account.bicep' = if (enableMlops) {
  name: 'mlops-storage'
  params: {
    storageAccountName: mlopsStorageAccountName
    location: location
    containers: [
      mlopsDatasetContainerName
      mlopsArtifactContainerName
      mlopsManifestContainerName
      mlopsEvaluationContainerName
    ]
  }
}

module mlopsIdentity './modules/managed-identity.bicep' = if (enableMlops) {
  name: 'mlops-identity'
  params: {
    identityName: mlopsIdentityName
    location: location
  }
}

resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: monitoring.outputs.logAnalyticsCustomerId
        sharedKey: monitoring.outputs.logAnalyticsSharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
      {
        name: gpuWorkloadProfileName
        workloadProfileType: 'Consumption-GPU-T4'
      }
    ]
  }
}

resource containerRegistryForMl 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = if (enableMlops) {
  name: acrName
}

module mlWorkspace './modules/aml-workspace.bicep' = if (enableMlops) {
  name: 'ml-workspace'
  params: {
    workspaceName: mlWorkspaceName
    location: location
    applicationInsightsId: monitoring.outputs.appInsightsId
    keyVaultId: keyVault.id
    storageAccountId: mlopsStorage.outputs.id
    containerRegistryId: containerRegistryForMl.id
  }
}

module ollamaApp './modules/ollama-app.bicep' = {
  name: 'ollama-app'
  params: {
    appName: ollamaAppName
    location: location
    containerAppEnvironmentId: containerEnv.id
    image: ollamaImage
    workloadProfileName: gpuWorkloadProfileName
    modelNames: [
      ollamaPlanningModel
      ollamaResponseModel
    ]
    minReplicas: ollamaMinReplicas
    maxReplicas: ollamaMaxReplicas
    cpu: ollamaCpu
    memory: ollamaMemory
    keepAlive: ollamaKeepAlive
  }
}

module apiApp './modules/container-app.bicep' = {
  name: 'api-app'
  params: {
    appName: apiAppName
    location: location
    containerAppEnvironmentId: containerEnv.id
    image: apiImage
    targetPort: 8000
    minReplicas: 0
    maxReplicas: environment == 'prod' ? 2 : 1
    registryServer: acr.outputs.loginServer
    envVars: [
      {
        name: 'APP_ENV'
        value: environment
      }
      {
        name: 'DATABASE_URL'
        value: 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.outputs.fqdn}:5432/${postgresDatabaseName}?ssl=require'
      }
      {
        name: 'CORS_ALLOWED_ORIGINS'
        value: corsAllowedOrigins
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: monitoring.outputs.appInsightsConnectionString
      }
      {
        name: 'TELEMETRY_SERVICE_NAME'
        value: 'traveltom-api'
      }
      {
        name: 'JSON_LOGS_ENABLED'
        value: 'true'
      }
      {
        name: 'ORCHESTRATOR_LLM_PROVIDER'
        value: 'ollama'
      }
      {
        name: 'OLLAMA_BASE_URL'
        value: 'http://${ollamaApp.outputs.fqdn}'
      }
      {
        name: 'OLLAMA_PLANNING_MODEL'
        value: ollamaPlanningModel
      }
      {
        name: 'OLLAMA_RESPONSE_MODEL'
        value: ollamaResponseModel
      }
      {
        name: 'OPENAI_BASE_URL'
        value: openaiBaseUrl
      }
      {
        name: 'ORCHESTRATOR_OPENAI_API_KEY'
        secretRef: 'openai-api-key'
      }
      {
        name: 'LOCAL_AUTH_TOKEN_SECRET'
        secretRef: 'local-auth-token-secret'
      }
      {
        name: 'TRAVELTOM_ML_RANKER_ARTIFACT_URI'
        value: promotedMlModelArtifactUri
      }
      {
        name: 'TRAVELTOM_ML_RANKER_PROMOTED_VERSION'
        value: promotedMlModelVersion
      }
      {
        name: 'TRAVELTOM_ML_RANKER_CACHE_DIR'
        value: '/tmp/traveltom-ml-cache'
      }
    ]
    secrets: [
      {
        name: 'openai-api-key'
        value: openaiApiKey
      }
      {
        name: 'local-auth-token-secret'
        value: localAuthTokenSecret
      }
    ]
    ingressExternal: true
    livenessPath: '/api/v1/health'
  }
}

module webApp './modules/container-app.bicep' = {
  name: 'web-app'
  params: {
    appName: webAppName
    location: location
    containerAppEnvironmentId: containerEnv.id
    image: webImage
    targetPort: 8080
    minReplicas: 0
    maxReplicas: 1
    registryServer: acr.outputs.loginServer
    envVars: [
      {
        name: 'VITE_API_BASE_URL'
        value: frontendApiBaseUrl
      }
      {
        name: 'VITE_APPINSIGHTS_CONNECTION_STRING'
        value: frontendAppInsightsConnectionString
      }
    ]
    secrets: []
    ingressExternal: true
    livenessPath: '/'
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource mlopsStorageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = if (enableMlops) {
  name: mlopsStorage.outputs.name
}

resource apiAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, apiApp.outputs.principalId, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: apiApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource webAcrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, webApp.outputs.principalId, acrPullRoleDefinitionId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: acrPullRoleDefinitionId
    principalId: webApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource mlopsStorageContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableMlops) {
  name: guid(mlopsStorage.outputs.id, mlopsIdentity.outputs.principalId, storageBlobDataContributorRoleDefinitionId)
  scope: mlopsStorageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleDefinitionId
    principalId: mlopsIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

resource apiMlopsStorageReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableMlops) {
  name: guid(mlopsStorage.outputs.id, apiApp.outputs.principalId, storageBlobDataReaderRoleDefinitionId)
  scope: mlopsStorageAccount
  properties: {
    roleDefinitionId: storageBlobDataReaderRoleDefinitionId
    principalId: apiApp.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

output acrLoginServer string = acr.outputs.loginServer
output apiAppName string = apiApp.name
output apiUrl string = apiApp.outputs.latestRevisionFqdn
output webAppName string = webApp.name
output webUrl string = webApp.outputs.latestRevisionFqdn
output ollamaAppName string = ollamaApp.name
output ollamaInternalFqdn string = ollamaApp.outputs.fqdn
output applicationInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output keyVaultName string = keyVault.name
output postgresServerFqdn string = postgres.outputs.fqdn
output mlopsEnabled bool = enableMlops
output mlopsStorageAccountName string = enableMlops ? mlopsStorage.outputs.name : ''
output mlopsStorageBlobEndpoint string = enableMlops ? mlopsStorage.outputs.primaryBlobEndpoint : ''
output mlopsWorkspaceName string = enableMlops ? mlWorkspace.outputs.name : ''
output mlopsIdentityClientId string = enableMlops ? mlopsIdentity.outputs.clientId : ''
output mlopsDatasetContainerName string = enableMlops ? mlopsDatasetContainerName : ''
output mlopsArtifactContainerName string = enableMlops ? mlopsArtifactContainerName : ''
output mlopsManifestContainerName string = enableMlops ? mlopsManifestContainerName : ''
output mlopsEvaluationContainerName string = enableMlops ? mlopsEvaluationContainerName : ''
