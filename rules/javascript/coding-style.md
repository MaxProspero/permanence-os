# JavaScript Coding Style

- Use var (not let/const) for broad browser compatibility
- No ES6 modules -- all code in script tags or IIFEs
- AbortController with timeout on all fetch calls
- No setInterval under 30000ms for polling
- DOM diffing: check current value before writing
- Canvas rendering: use devicePixelRatio scaling
- Event delegation where possible
- No external JS frameworks (vanilla JS only)
- Error handling: .catch() on all fetch promises
