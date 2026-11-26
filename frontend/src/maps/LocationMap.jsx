/** @jsx localizedElement */
/** @jsxFrag React.Fragment */
import {localizedElement} from "../localization";
import React, {useEffect} from 'react';
import L from 'leaflet';
import {MapContainer, TileLayer, Marker, useMapEvents} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

function pin(text = '', selected = false) {
  return L.divIcon({className: selected ? 'selected-map-pin' : 'result-map-pin', html: text, iconSize: [26, 26], iconAnchor: [13, 13]});
}
const selectedIcon = pin('', true);

function MapSelection({point, results, onPick, onResult}) {
  const map = useMapEvents({click: ({latlng}) => onPick({...latlng, source: 'map'})});
  const lat = point?.lat, lng = point?.lng;
  const valid = Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat)<=90 && Math.abs(lng)<=180;
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  useEffect(() => {
    if (valid) map.setView([lat, lng], 16);
  }, [map, lat, lng, valid]);
  useEffect(() => {
    if (results.length) map.fitBounds(results.map(p => [p.lat, p.lng]), {maxZoom: 16, padding: [30, 30]});
  }, [map, results]);
  return <>
    {results.map((p, i) => <Marker key={i} position={[p.lat, p.lng]} icon={pin(String(i+1))} eventHandlers={{click: () => onResult(p)}}/>)}
    {valid && <Marker position={[lat, lng]} draggable icon={selectedIcon} eventHandlers={{dragend: event => onPick({...event.target.getLatLng(), source: 'map'})}}/>}
  </>;
}
export default function LocationMap(props) {
  return <div className="location-map-shell"><MapContainer className="location-map" center={[41.55,60.63]} zoom={11} scrollWheelZoom={false}>
    <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'/>
    <MapSelection {...props}/>
  </MapContainer></div>;
}
