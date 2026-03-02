#!/usr/bin/env node
// WiFi DensePose — Node.js static file server
// Serves the ui/ directory on PORT (default 3000)

'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = parseInt(process.env.PORT || '3000', 10);
const UI_DIR = path.join(__dirname, 'ui');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.js':   'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif':  'image/gif',
  '.svg':  'image/svg+xml',
  '.ico':  'image/x-icon',
  '.woff': 'font/woff',
  '.woff2':'font/woff2',
  '.ttf':  'font/ttf',
  '.map':  'application/json',
};

const server = http.createServer((req, res) => {
  // Use WHATWG URL API to safely parse the request URL
  const parsedUrl = new URL(req.url, `http://localhost:${PORT}`);
  let pathname = parsedUrl.pathname;

  // Resolve to an absolute path and reject any traversal outside UI_DIR
  let filePath = path.resolve(UI_DIR, pathname.slice(1));
  if (!filePath.startsWith(UI_DIR + path.sep) && filePath !== UI_DIR) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  // Default to index.html for directory requests (single stat call)
  try {
    const stats = fs.statSync(filePath);
    if (stats.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
  } catch (err) {
    if (err.code !== 'ENOENT') {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Internal server error');
      return;
    }
    // File not found — fall back to index.html for SPA-style navigation
    filePath = path.join(UI_DIR, 'index.html');
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === 'EACCES') {
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
      } else if (err.code === 'ENOENT') {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not found');
      } else {
        res.writeHead(500, { 'Content-Type': 'text/plain' });
        res.end('Internal server error');
      }
      return;
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(`\n🚀 WiFi DensePose UI running at http://localhost:${PORT}`);
  console.log(`   Backend API expected at http://localhost:8000`);
  console.log(`   Tests: http://localhost:${PORT}/tests/test-runner.html`);
  console.log('\n   Press Ctrl+C to stop\n');
});
