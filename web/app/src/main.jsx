import { render } from 'preact';
import { App } from './App.jsx';
import { installSdk } from './plugins.js';
import './app.css';

// window.sfz — the runtime SDK plugin UI modules (plugins/<id>/ui.js) are
// written against; must exist before any of them is imported (plugins.js).
installSdk();

// On the web the theme is served by the panel as /static/style.css (linked in
// index.html). The app shell has no panel to link to before a device is picked,
// so the Capacitor build folds the compiled shared stylesheet into the bundle.
if (import.meta.env.VITE_CAPACITOR === '1') import('../../ui/style.css');

render(<App />, document.getElementById('app'));
