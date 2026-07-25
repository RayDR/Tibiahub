import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

// Fix Leaflet Default Icon
L.Icon.Default.mergeOptions({
    iconRetinaUrl: iconRetinaUrl,
    iconUrl: iconUrl,
    shadowUrl: shadowUrl,
});

// Coordinate conversion helper (Simple linear mapping for demo)
// Tibia coordinates (approx): X: 31000-34000, Y: 31000-33000
// We map this to Leaflet Lat/Lng
const tibiaToLatLng = (x: number, y: number): [number, number] => {
    // This is a naive projection. Real Tibia maps need CoordinateReferenceSystem (CRS).Simple
    // For now, we center around Thais (32369, 32241) -> (0, 0)
    const lat = -(y - 32241) * 0.1;
    const lng = (x - 32369) * 0.1;
    return [lat, lng];
};

interface TibiaMapProps {
    markers?: Array<{ x: number; y: number; label: string }>;
    center?: { x: number; y: number };
    zoom?: number;
}

const RecenterMap: React.FC<{ center: { x: number; y: number } }> = ({ center }) => {
    const map = useMap();
    useEffect(() => {
        const [lat, lng] = tibiaToLatLng(center.x, center.y);
        map.setView([lat, lng]);
    }, [center, map]);
    return null;
};

const TibiaMap: React.FC<TibiaMapProps> = ({ markers = [], center = { x: 32369, y: 32241 }, zoom = 13 }) => {
    const [initialLat, initialLng] = tibiaToLatLng(center.x, center.y);

    return (
        <div className="w-full h-[400px] rounded-xl overflow-hidden border border-line shadow-lg relative z-0">
            <MapContainer
                center={[initialLat, initialLng]}
                zoom={zoom}
                scrollWheelZoom={false}
                style={{ height: '100%', width: '100%' }}
                crs={L.CRS.Simple} // Essential for flat maps like games
            >
                <RecenterMap center={center} />

                {/*
            Using a dark background or specific tile server.
            Since we don't have a reliable Tibia Tile Server API key in this context,
            we use a placeholder grid or open street map with significant zoom (not accurate for Tibia but demonstrates functionality)
            Ideally: url="https://tibiamaps.io/tiles/{z}/{x}/{y}.png"
        */}
                <TileLayer
                    attribution='&copy; <a href="https://tibiamaps.io">TibiaMaps.io</a>'
                    url="https://tibiamaps.github.io/tibia-map-data/mapper/Minimap_Color_{z}_{x}_{y}.png"
                    // Note: The above URL is hypothetical. Real integration requires a valid tile source or custom tiles.
                    // Fallback to dark tiles for aesthetic
                    noWrap
                />

                {markers.map((marker, idx) => {
                    const [lat, lng] = tibiaToLatLng(marker.x, marker.y);
                    return (
                        <Marker key={idx} position={[lat, lng]}>
                            <Popup>{marker.label}</Popup>
                        </Marker>
                    );
                })}
            </MapContainer>

            <div className="absolute bottom-2 right-2 bg-surface-base/80 p-2 rounded text-xs text-content-secondary z-[1000]">
                Center: {center.x}, {center.y}
            </div>
        </div>
    );
};

export default TibiaMap;
