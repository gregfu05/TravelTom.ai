# Azure Deployment

This folder contains the Azure runtime-first deployment assets for TravelTom.

## Provisioned resources

- Azure Container Registry
- Azure Container Apps environment
- Azure Container Apps for `api` and `web`
- Azure Database for PostgreSQL Flexible Server
- Azure Key Vault
- Log Analytics workspace
- Application Insights

## Validate Bicep

```powershell
az deployment group validate `
  --resource-group <rg-name> `
  --parameters infra/azure/main.dev.bicepparam `
  --template-file infra/azure/main.bicep
```

## Deploy dev

```powershell
az deployment group create `
  --resource-group <rg-name> `
  --parameters infra/azure/main.dev.bicepparam `
  --template-file infra/azure/main.bicep
```

## Deploy prod

```powershell
az deployment group create `
  --resource-group <rg-name> `
  --parameters infra/azure/main.prod.bicepparam `
  --template-file infra/azure/main.bicep
```

## Destroy resource group

```powershell
az group delete --name <rg-name> --yes --no-wait
```

## Notes

- Replace placeholder image names and passwords in the `.bicepparam` files before use.
- The GitHub Actions workflows are the intended deployment entrypoint after initial bootstrap.
- `frontendApiBaseUrl` should point to the public API endpoint including `/api/v1`.
