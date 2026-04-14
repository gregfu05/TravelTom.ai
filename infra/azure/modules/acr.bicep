param acrName string
param location string
param publicNetworkAccess string = 'Enabled'
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: publicNetworkAccess
  }
}

output loginServer string = registry.properties.loginServer
