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

output acrLoginServer string = acr.outputs.loginServer
output apiAppName string = apiApp.name
output apiUrl string = apiApp.outputs.latestRevisionFqdn
output webAppName string = webApp.name
output webUrl string = webApp.outputs.latestRevisionFqdn
output applicationInsightsConnectionString string = monitoring.outputs.appInsightsConnectionString
output keyVaultName string = keyVault.name
output postgresServerFqdn string = postgres.outputs.fqdn
