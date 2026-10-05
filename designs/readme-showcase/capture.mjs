// Capture the current client without sending input to the host computer.
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const directory = path.dirname(fileURLToPath(import.meta.url));
const clientURL = process.env.REMOTE_MOUSE_CLIENT_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
});
const actions = ['rewind', 'play_pause', 'forward', 'volume_down', 'mute', 'volume_up', 'fullscreen'];
const errors = [];
await mkdir(path.join(directory, 'screens'), { recursive: true });

try {
  for (const language of ['en', 'zh']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 2 });
    await context.addInitScript(lang => {
      localStorage.setItem('remote-mouse-lang', lang);
      localStorage.setItem('remote-mouse-input-mode', 'draft');
    }, language);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await page.routeWebSocket('**/ws', socket => {
      let revision = 0, queryId = 0, volume = 45;
      socket.onMessage(message => {
        if (typeof message === 'string') return;
        const packet = Buffer.from(message);
        const snapshot = { type: 'media_snapshot', version: 1, revision: ++revision,
          capabilities: actions, unavailable: {},
          state: { volume, muted: false, playing: null, fullscreen: null } };
        if (packet[0] === 8) {
          socket.send(JSON.stringify({ ...snapshot, queryId: ++queryId }));
        } else if (packet[0] === 7) {
          const action = actions[packet[1] - 1];
          const requestId = packet.readUInt32BE(2);
          if (action === 'volume_up') volume += 5;
          socket.send(JSON.stringify({ type: 'media_result', version: 1, requestId, action,
            status: ['volume_down', 'volume_up', 'mute'].includes(action) ? 'verified' : 'issued' }));
          socket.send(JSON.stringify({ ...snapshot, requestId, state: { ...snapshot.state, volume } }));
        }
      });
    });
    await page.goto(clientURL);
    await page.locator('#status-indicator.status-connected').waitFor();
    // Only freeze decorative breathing/carets; preserve production geometry and UI.
    await page.addStyleTag({ content: '* { animation: none !important; caret-color: transparent !important; }' });
    const capture = async name => {
      await page.waitForTimeout(350);
      await page.screenshot({ path: path.join(directory, 'screens', `${name}-${language}.png`) });
    };
    await capture('computer');
    await page.locator('#btn-keyboard').click();
    await page.locator('#draft-input').fill(language === 'zh' ? '今晚看什么？' : 'What shall we watch?');
    await capture('draft');
    await page.locator('#btn-send').click();
    await capture('sent');
    await page.locator('#mode-tv').click();
    await page.locator('[data-media="volume_up"]').waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.querySelector('[data-media="volume_up"]').disabled);
    await capture('tv');
    await page.locator('[data-media="volume_up"]').click();
    await capture('volume');
    await page.locator('#btn-settings').click();
    await page.locator('#theme-toggle').check();
    await page.locator('#btn-close-settings').click();
    await capture('tv-light');
    await page.locator('#btn-settings').click();
    await capture('settings');
    await context.close();
  }
  if (errors.length) throw new Error(errors.join('\n'));
  await writeFile(path.join(directory, 'capture-info.json'), JSON.stringify({
    viewport: { width: 390, height: 780 }, deviceScaleFactor: 2,
    source: 'web-client/index.html + web-client/src',
    connection: 'Capture-only WebSocket fixture; no host input or audio is controlled.',
  }, null, 2) + '\n');
  console.log('Captured 14 client states; no browser runtime errors.');
} finally {
  await browser.close();
}
