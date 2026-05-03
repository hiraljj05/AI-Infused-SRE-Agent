@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Name of the AKS cluster')
param aksClusterName string = 'sre-demo-aks'

@description('Admin username for Linux nodes (SSH)')
param linuxAdminUsername string = 'sreadmin'

@description('SSH public key for AKS nodes')
param linuxAdminSshKey string

@description('Node VM size (cost-optimized)')
param nodeVmSize string = 'Standard_B2s'

@description('Node count - single node is intentional to fit free credit')
param nodeCount int = 1

@description('Tag applied to all resources')
param costCenterTag string = 'sre-agent-demo'

// AKS cluster. Kubernetes version is intentionally omitted so Azure picks the
// current default for the region (avoids LTS-only versions on free tier).
resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: aksClusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Base'
    tier: 'Free'
  }
  properties: {
    dnsPrefix: '${aksClusterName}-dns'
    enableRBAC: true
    agentPoolProfiles: [
      {
        name: 'nodepool1'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        osDiskSizeGB: 64
        mode: 'System'
        type: 'VirtualMachineScaleSets'
        enableAutoScaling: false
        maxPods: 60
      }
    ]
    linuxProfile: {
      adminUsername: linuxAdminUsername
      ssh: {
        publicKeys: [
          {
            keyData: linuxAdminSshKey
          }
        ]
      }
    }
    networkProfile: {
      networkPlugin: 'kubenet'
      loadBalancerSku: 'standard'
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalytics.id
        }
      }
    }
  }
  tags: {
    costCenter: costCenterTag
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${aksClusterName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: {
    costCenter: costCenterTag
  }
}

// NOTE: Azure Bot Service deliberately NOT deployed here.
// Reasons:
// 1. It requires an existing Azure AD app registration (MSA App ID) which must be created
//    out-of-band (az ad app create) and supplied as a parameter.
// 2. The globally-unique bot display name needs to be reserved per tenant.
// We will create the Bot Service separately once Teams integration is needed.

output aksClusterName string = aks.name
output aksFqdn string = aks.properties.fqdn
output logAnalyticsId string = logAnalytics.id
