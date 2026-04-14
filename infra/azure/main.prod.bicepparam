using './main.bicep'

param environment = 'prod'
param location = 'westeurope'
param apiImage = 'example.azurecr.io/traveltom-api:prod'
param webImage = 'example.azurecr.io/traveltom-web:prod'
param ollamaImage = 'ollama/ollama:latest'
param ollamaPlanningModel = 'llama3.1:8b'
param ollamaResponseModel = 'llama3.1:8b'
param ollamaMinReplicas = 1
param ollamaMaxReplicas = 1
param ollamaCpu = 4
param ollamaMemory = '16Gi'
param ollamaKeepAlive = '30m'
param postgresAdminLogin = 'traveltomadmin'
param postgresAdminPassword = 'replace-me'
param corsAllowedOrigins = 'https://traveltom.example.com'
param frontendApiBaseUrl = 'https://traveltom-api.example.com/api/v1'
param enableMlops = false
param promotedMlModelArtifactUri = ''
param promotedMlModelVersion = ''
param managedByTag = 'codex'
param ownerTag = 'traveltom'
param postgresAllowAzureServicesFirewall = true
