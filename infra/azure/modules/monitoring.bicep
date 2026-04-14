param location string
param logAnalyticsWorkspaceName string
param appInsightsName string
param tags object = {}

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
  }
}

resource workspaceSharedKeys 'Microsoft.OperationalInsights/workspaces/sharedKeys@2022-10-01' existing = {
  parent: workspace
  name: 'default'
}

output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsId string = appInsights.id
output logAnalyticsCustomerId string = workspace.properties.customerId
output logAnalyticsSharedKey string = listKeys(workspace.id, workspace.apiVersion).primarySharedKey
