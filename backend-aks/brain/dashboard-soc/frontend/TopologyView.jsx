import React, { useState, useEffect } from 'react';

const TopologyView = () => {
    const [topology, setTopology] = useState({ nodes: [] });

    useEffect(() => {
        fetch('/api/v1/topology')
            .then((res) => res.json())
            .then((data) => setTopology(data))
            .catch((err) => console.error("Error cargando topología", err));
    }, []);

    return (
        <div className="topology-panel">
            <h2>Topología del Cluster AKS</h2>
            <div className="nodes-container" style={{ display: 'flex', gap: '20px' }}>
                {topology.nodes.map((node, i) => (
                    <div key={i} className="node-box" style={{ border: '2px solid #00acc1', padding: '15px', borderRadius: '8px' }}>
                        <h3>{node.role}</h3>
                        <p><strong>NodePool:</strong> {node.name}</p>
                        <h4>Pods Corriendo:</h4>
                        <ul>
                            {node.pods.map((pod, j) => (
                                <li key={j}>{pod}</li>
                            ))}
                        </ul>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default TopologyView;
