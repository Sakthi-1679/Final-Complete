import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles.css';
import App from './App';

console.log('Initializing React app...');

const rootElement = document.getElementById('root');
console.log('Root element:', rootElement);

if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
console.log('React root created');

try {
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  console.log('App rendered successfully');
} catch (error) {
  console.error('Error rendering app:', error);
  rootElement.innerHTML = `<div style="color: red; padding: 20px;"><h1>Error Loading App</h1><p>${String(error)}</p></div>`;
}