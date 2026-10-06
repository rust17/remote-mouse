/// <reference types="vitest" />
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const eruda = readFileSync(require.resolve('eruda'));
const debugBootstrap = readFileSync(new URL('./src/core/debug-bootstrap.js', import.meta.url), 'utf8');

export default defineConfig({
  plugins: [
    {
      name: 'mobile-debug',
      transformIndexHtml: {
        order: 'pre',
        handler: () => [{ tag: 'script', attrs: { id: 'debug-bootstrap' }, children: debugBootstrap, injectTo: 'head-prepend' }],
      },
      configureServer(server) {
        server.middlewares.use('/debug/eruda.js', (_request, response) => {
          response.setHeader('Content-Type', 'text/javascript; charset=utf-8');
          response.end(eruda);
        });
      },
      generateBundle() {
        this.emitFile({ type: 'asset', fileName: 'debug/eruda.js', source: eruda });
      },
    },
    VitePWA({
      registerType: 'autoUpdate',
      workbox: { globIgnores: ['**/debug/eruda.js'] },
      includeAssets: ['pwa-icon.png', 'pwa-192x192.png', 'pwa-512x512.png'],
      manifest: {
        name: 'Remote Mouse',
        short_name: 'RemoteMouse',
        description: 'Control your computer remotely',
        theme_color: '#0f1115',
        background_color: '#0f1115',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}']
  },
});
