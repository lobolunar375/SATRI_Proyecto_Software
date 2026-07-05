import React, { useState, useEffect } from 'react';

const DevicesView = () => {
    const [devices, setDevices] = useState([]);

    useEffect(() => {
        fetch('/api/v1/devices')
            .then((res) => res.json())
            .then((data) => setDevices(data.devices))
            .catch((err) => console.error("Falta autenticación JWT como Admin", err));
    }, []);

    const handleIsolate = (deviceId) => {
        fetch(`/api/v1/devices/${deviceId}/isolate`, { method: 'POST' })
            .then(res => res.json())
            .then(data => alert(data.message));
    };

    return (
        <div className="devices-panel">
            <h2>Panel de Dispositivos (Solo Admin)</h2>
            <table border="1" cellPadding="10">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Hostname</th>
                        <th>IP</th>
                        <th>Estado</th>
                        <th>Acción</th>
                    </tr>
                </thead>
                <tbody>
                    {devices.map(dev => (
                        <tr key={dev.id}>
                            <td>{dev.id}</td>
                            <td>{dev.hostname}</td>
                            <td>{dev.ip}</td>
                            <td style={{ color: dev.status === 'ONLINE' ? 'green' : 'red' }}>{dev.status}</td>
                            <td>
                                <button onClick={() => handleIsolate(dev.id)} style={{ background: 'red', color: 'white' }}>
                                    Aislar Host
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default DevicesView;
