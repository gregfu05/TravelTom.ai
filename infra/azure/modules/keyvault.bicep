param keyVaultName string
param location string
param secrets object
param publicNetworkAccess string = 'Enabled'
param tags object = {}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    publicNetworkAccess: publicNetworkAccess
    enabledForDeployment: false
    enabledForTemplateDeployment: true
    enabledForDiskEncryption: false
  }
}

resource secretItems 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = [for secretName in keys(secrets): {
  name: '${vault.name}/${secretName}'
  properties: {
    value: string(secrets[secretName])
  }
}]

output vaultUri string = vault.properties.vaultUri
