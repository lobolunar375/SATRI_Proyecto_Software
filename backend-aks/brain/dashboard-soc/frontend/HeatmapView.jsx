import React, { useState, useEffect } from 'react';

// Componente React Mock para visualizar el mapa de calor
const HeatmapView = () => {
    const [events, setEvents] = useState([]);

    useEffect(() => {
        // En producción esto se conectaría al websocket_handler.py
        const ws = new WebSocket('ws://localhost:8000/ws/alerts');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.geo_lat && data.geo_lon) {
                setEvents((prev) => [...prev, data]);
            }
        };
        return () => ws.close();
    }, []);

    return (
        <div className="heatmap-container">
            <h2>Mapa de Calor de Ataques (En Vivo)</h2>
            <div className="map-placeholder" style={{ background: '#1e1e1e', height: '400px', padding: '20px', color: 'white' }}>
                {events.length === 0 ? (
                    <p>Esperando telemetría enriquecida por MML...</p>
                ) : (
                    <ul>
                        {events.map((ev, i) => (
                            <li key={i}>
                                Ataque detectado desde: {ev.geo_city}, {ev.geo_country} (Severidad: {ev.severity})
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default HeatmapView;
