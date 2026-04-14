using './main.bicep'

param environment = 'dev'
param location = 'westeurope'
param apiImage = 'example.azurecr.io/traveltom-api:dev'
param webImage = 'example.azurecr.io/traveltom-web:dev'
param ollamaImage = 'ollama/ollama:latest'
param ollamaPlanningModel = 'llama3.1:8b'
param ollamaResponseModel = 'llama3.1:8b'
param ollamaMinReplicas = 0
param ollamaMaxReplicas = 1
param ollamaCpu = 4
param ollamaMemory = '8Gi'
param ollamaKeepAlive = '10m'
param postgresAdminLogin = 'traveltomadmin'
param postgresAdminPassword = 'replace-me'
param corsAllowedOrigins = 'https://traveltom-dev-web.example.com'
param frontendApiBaseUrl = 'https://traveltom-dev-api.example.com/api/v1'
