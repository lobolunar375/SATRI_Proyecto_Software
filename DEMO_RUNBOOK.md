# 🎯 SATRI v2 — Demo Runbook (Día de la Demo)

> **IMPORTANTE:** Este procedimiento crea recursos de Azure que CUESTAN DINERO.
> Tiempo máximo: **6 horas**. Destruir INMEDIATAMENTE después.

---

## Pre-requisitos

- [ ] Azure CLI instalado y logueado (`az login`)
- [ ] kubectl instalado
- [ ] Cosmos DB free tier ya activo con datos de usuarios reales
- [ ] Docker images publicadas en ACR o Docker Hub
- [ ] Budget Alert de $5 USD configurado

---

## Paso 1: Crear Resource Group

```bash
az group create --name rg-satri-demo --location eastus
```

**Verificar:**
```bash
az group show --name rg-satri-demo --query "properties.provisioningState" -o tsv
# Esperado: Succeeded
```

---

## Paso 2: Configurar Budget Alert de $5 USD

```bash
az consumption budget create \
  --budget-name satri-budget-5usd \
  --resource-group rg-satri-demo \
  --amount 5 \
  --time-grain Monthly \
  --category Cost \
  --start-date $(date +%Y-%m-01) \
  --end-date 2027-12-31
```

---

## Paso 3: Crear Cluster AKS con 2 Node Pools

```bash
# Nodo A: Frontline (correlación e ingesta)
az aks create \
  --resource-group rg-satri-demo \
  --name satri-aks-demo \
  --node-count 1 \
  --nodepool-name frontline \
  --node-vm-size Standard_B2s \
  --generate-ssh-keys

# Nodo B: Brain (análisis y respuesta)
az aks nodepool add \
  --resource-group rg-satri-demo \
  --cluster-name satri-aks-demo \
  --name brain \
  --node-count 1 \
  --node-vm-size Standard_B2s
```

**Verificar:**
```bash
az aks show --resource-group rg-satri-demo --name satri-aks-demo --query "provisioningState" -o tsv
# Esperado: Succeeded
```

---

## Paso 4: Conectar kubectl

```bash
az aks get-credentials --resource-group rg-satri-demo --name satri-aks-demo
kubectl get nodes
# Esperado: 2 nodos (frontline + brain)
```

---

## Paso 5: Desplegar Namespaces y Servicios

```bash
# Namespaces
kubectl apply -f k8s-v2/00-namespaces.yaml

# Secrets (reemplazar primero con keys reales de Cosmos DB)
kubectl apply -f k8s-v2/01-secrets.yaml

# Frontline
kubectl apply -f k8s-v2/frontline/correlation-engine.yaml

# Brain
kubectl apply -f k8s-v2/brain/brain-services.yaml
```

**Verificar:**
```bash
kubectl get pods -n frontline
kubectl get pods -n brain
# Todos deben estar Running
```

---

## Paso 6: Acceder al Dashboard

```bash
# Obtener IP externa del Dashboard Admin
kubectl get svc dashboard-admin -n brain
# Usar la EXTERNAL-IP para acceder al dashboard
```

---

## Paso 7: Demo en Vivo

### Qué mostrar:

1. **Dashboard Admin** — Eventos de usuarios reales acumulados en Cosmos DB
2. **Correlation Engine** — Procesamiento batch de eventos en tiempo real
3. **Topología de Pods** — `kubectl get pods -n frontline -o wide` y `kubectl get pods -n brain -o wide`
4. **Arquitectura distribuida** — Separación física Frontline/Brain en nodos distintos
5. **App de escritorio** — Demostrar detección de ransomware simulado
6. **Extensión** — Navegar a sitio de prueba con certificado inválido

### Sitios de prueba para la extensión:
- Certificado expirado: `https://expired.badssl.com/`
- Certificado wrong host: `https://wrong.host.badssl.com/`
- Self-signed: `https://self-signed.badssl.com/`

---

## ⚠️ Paso 8: DESTRUIR TODO (INMEDIATAMENTE después de la demo)

```bash
# 1. Eliminar namespaces (detiene todos los pods)
kubectl delete namespace frontline brain

# 2. Eliminar cluster AKS
az aks delete --resource-group rg-satri-demo --name satri-aks-demo --yes --no-wait

# 3. Eliminar resource group completo
az group delete --name rg-satri-demo --yes --no-wait
```

---

## Paso 9: Verificación Post-Demo

**Ejecutar 30 minutos después de la destrucción:**

```bash
# Verificar que no queda nada
az group show --name rg-satri-demo 2>&1
# Esperado: ERROR (no existe)

az aks list --query "[?name=='satri-aks-demo']" -o table
# Esperado: vacío

# Verificar que no hay costos inesperados
az consumption usage list --query "[?contains(instanceName, 'satri')]" -o table
# Esperado: vacío o solo Cosmos DB free tier
```

---

## Checklist Final

- [ ] Cluster AKS eliminado
- [ ] Resource Group eliminado
- [ ] No hay pods corriendo
- [ ] Cosmos DB free tier sigue activo (es permanente gratis)
- [ ] Azure Functions sigue activa (es permanente gratis)
- [ ] No hay costos inesperados en el portal de Azure
- [ ] Budget alert no se disparó

---

**Costo estimado de la demo (6h, 2x Standard_B2s):** ~$0.50 - $1.00 USD
