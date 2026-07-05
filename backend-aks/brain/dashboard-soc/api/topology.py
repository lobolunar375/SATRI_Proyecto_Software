from fastapi import APIRouter
import os
import logging

router = APIRouter(prefix="/api/v1/topology", tags=["Topology"])
logger = logging.getLogger("topology")

@router.get("/")
async def get_cluster_topology():
    topology = {"nodes": []}
    
    # Check if running in Kubernetes
    if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount/token'):
        try:
            from kubernetes import client, config
            config.load_incluster_config()
            v1 = client.CoreV1Api()
            pods = v1.list_pod_for_all_namespaces(watch=False)
            nodes = v1.list_node()
            
            node_map = {n.metadata.name: [] for n in nodes.items}
            for pod in pods.items:
                if pod.spec.node_name and pod.spec.node_name in node_map:
                    node_map[pod.spec.node_name].append(pod.metadata.name)
            
            for node_name, pod_list in node_map.items():
                topology["nodes"].append({
                    "name": node_name,
                    "role": "AKS Node",
                    "pods": pod_list
                })
        except Exception as e:
            logger.error(f"Error querying K8s API: {e}")
            topology["nodes"].append({
                "name": "Error",
                "role": "K8s API Failed",
                "pods": [str(e)]
            })
    else:
        # Fallback to Docker for local dev
        try:
            import docker
            client = docker.from_env()
            containers = client.containers.list()
            
            satri_containers = []
            for c in containers:
                if "satri" in c.name:
                    satri_containers.append(c.name)
            
            topology["nodes"].append({
                "name": "local-docker-host",
                "role": "Docker Compose",
                "pods": satri_containers
            })
        except Exception as e:
            logger.error(f"Error querying Docker API: {e}")
            topology["nodes"].append({
                "name": "local-docker-host",
                "role": "Docker API Not Found",
                "pods": ["Requires /var/run/docker.sock to be mounted"]
            })
            
    return topology
