param workspaceName string
param location string
param applicationInsightsId string
param keyVaultId string
param storageAccountId string
param containerRegistryId string
param publicNetworkAccess string = 'Enabled'

resource workspace 'Microsoft.MachineLearningServices/workspaces@2022-05-01' = {
  name: workspaceName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    applicationInsights: applicationInsightsId
    containerRegistry: containerRegistryId
    keyVault: keyVaultId
    publicNetworkAccess: publicNetworkAccess
    storageAccount: storageAccountId
    v1LegacyMode: false
  }
}

output id string = workspace.id
output name string = workspace.name
output principalId string = workspace.identity.principalId
