param keyVaultName string
param location string
@secure()
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

resource secretItems 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = [for secret in items(secrets): {
  name: '${vault.name}/${secret.key}'
  properties: {
    value: string(secret.value)
  }
}]

output id string = vault.id
output name string = vault.name
output vaultUri string = vault.properties.vaultUri
