import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const directory = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(directory, '../../docs/images');
const previewURL = process.env.REMOTE_MOUSE_SHOWCASE_URL || 'http://127.0.0.1:4311/readme-showcase/showcase.html';
const browser = await chromium.launch({
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
});
const errors = [];
await mkdir(output, { recursive: true });

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 880 }, deviceScaleFactor: 1 });
  page.on('pageerror', error => errors.push(error.message));
  for (const lang of ['en', 'zh']) {
    await page.setViewportSize({ width: 1440, height: 880 });
    await page.goto(`${previewURL}?render&lang=${lang}`);
    for (const kind of ['hero', 'gallery']) {
      await page.evaluate(options => window.renderShowcase(options), { kind, lang });
      await page.evaluate(async () => {
        await document.fonts.ready;
        await Promise.all([...document.images].map(image => image.decode()));
      });
      const png = path.join(output, `${kind}-${lang}.png`);
      await page.screenshot({ path: png, clip: { x: 0, y: 0, width: 1440, height: kind === 'hero' ? 800 : 880 } });
    }
    await page.setViewportSize({ width: 1120, height: 620 });
    const frames = path.join(directory, 'frames', lang);
    await mkdir(frames, { recursive: true });
    for (let frame = 0; frame < 96; frame++) {
      await page.evaluate(options => window.renderShowcase(options), { kind: 'demo', lang, time: frame / 8 });
      await page.evaluate(async () => Promise.all([...document.images].map(image => image.decode())));
      await page.screenshot({ path: path.join(frames, `${String(frame).padStart(3, '0')}.png`),
        clip: { x: 0, y: 0, width: 1120, height: 620 } });
    }
    execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '8', '-i', path.join(frames, '%03d.png'),
      '-filter_complex', '[0:v]split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
      '-loop', '0', path.join(output, `walkthrough-${lang}.gif`)]);
  }
  // Verify the reusable preview also fits a narrow viewport.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(previewURL);
  for (const kind of ['hero', 'gallery', 'demo']) {
    await page.evaluate(kind => window.renderShowcase({ kind }), kind);
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    if (!fits) throw new Error(`Preview overflows in ${kind}`);
  }
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('Exported EN/ZH heroes, galleries and 12-second GIFs. Desktop/mobile preview passed without runtime errors.');
} finally {
  await browser.close();
}
