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
param cpu string = '0.5'
param memory string = '1Gi'
param readinessPath string = ''
param startupPath string = ''
param revisionSuffix string = ''
param tags object = {}

var probes = concat(
  [
    {
      type: 'Liveness'
      httpGet: {
        path: livenessPath
        port: targetPort
      }
      initialDelaySeconds: 10
      periodSeconds: 30
      failureThreshold: 3
    }
  ],
  empty(readinessPath)
    ? []
    : [
        {
          type: 'Readiness'
          httpGet: {
            path: readinessPath
            port: targetPort
          }
          initialDelaySeconds: 5
          periodSeconds: 15
          failureThreshold: 4
        }
      ],
  empty(startupPath)
    ? []
    : [
        {
          type: 'Startup'
          httpGet: {
            path: startupPath
            port: targetPort
          }
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 30
        }
      ]
)

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      activeRevisionsMode: 'Multiple'
      revisionSuffix: empty(revisionSuffix) ? null : revisionSuffix
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
          probes: probes
          resources: {
            cpu: json(cpu)
            memory: memory
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
output principalId string = app.identity.principalId
