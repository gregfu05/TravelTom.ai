param appName string
param location string
param containerAppEnvironmentId string
param image string
param targetPort int
param minReplicas int
param maxReplicas int
param registryServer string
param envVars array
param secrets array
param ingressExternal bool
param livenessPath string

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      activeRevisionsMode: 'Multiple'
      ingress: {
        external: ingressExternal
        targetPort: targetPort
        transport: 'auto'
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: registryServer
          identity: 'system'
        }
      ]
      secrets: [for secret in secrets: {
        name: secret.name
        value: secret.value
      }]
    }
    template: {
      containers: [
        {
          name: appName
          image: image
          env: [for envVar in envVars: {
            name: envVar.name
            value: contains(envVar, 'value') ? envVar.value : null
            secretRef: contains(envVar, 'secretRef') ? envVar.secretRef : null
          }]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: livenessPath
                port: targetPort
              }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
          resources: {
            cpu: 0.5
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

output latestRevisionName string = app.properties.latestRevisionName
output latestRevisionFqdn string = 'https://${app.properties.configuration.ingress.fqdn}'
