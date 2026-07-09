import { render } from 'preact';
import { App } from './App.jsx';
import './app.css';

// On the web the theme is served by the panel as /static/style.css (linked in
// index.html). The app shell has no panel to link to before a device is picked,
// so the Capacitor build folds the compiled shared stylesheet into the bundle.
if (import.meta.env.VITE_CAPACITOR === '1') import('../../ui/style.css');

render(<App />, document.getElementById('app'));
