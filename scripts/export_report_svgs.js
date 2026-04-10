#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const DEFAULT_HTML = path.resolve(__dirname, '..', 'docs', 'reports', 'report_figures_frontend_20260409.html');
const DEFAULT_OUTPUT = path.resolve(__dirname, '..', 'docs', 'reports', 'frontend_exports');

const FIGURE_NAMES = {
  'fig-architecture': 'figure1_overall_architecture',
  'fig-phase-flow': 'figure2_phase123_pipeline',
  'fig-hdd-summary': 'figure3_hdd_cross_model_summary',
  'fig-hdd-delta': 'figure4_hdd_delta_by_disk_model',
  'fig-mc1-phase2': 'figure5_mc1_phase2_quality',
  'fig-mc1-phase3': 'figure6_mc1_phase3_summary'
};

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function parseViewBox(svg) {
  const viewBox = svg.getAttribute('viewBox');
  if (!viewBox) return null;
  const parts = viewBox.trim().split(/\s+/).map(Number);
  if (parts.length !== 4 || parts.some(Number.isNaN)) return null;
  const [x, y, width, height] = parts;
  return { x, y, width, height };
}

function decorateSvg(svg, document) {
  if (!svg.getAttribute('style')) {
    svg.setAttribute('style', "font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;");
  } else if (!svg.getAttribute('style').includes('font-family')) {
    svg.setAttribute(
      'style',
      `${svg.getAttribute('style')} font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;`
    );
  }

  const view = parseViewBox(svg);
  if (view) {
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('x', String(view.x));
    bg.setAttribute('y', String(view.y));
    bg.setAttribute('width', String(view.width));
    bg.setAttribute('height', String(view.height));
    bg.setAttribute('fill', '#ffffff');
    svg.insertBefore(bg, svg.firstChild);
  }
}

async function main() {
  const htmlPath = path.resolve(process.argv[2] || DEFAULT_HTML);
  const outDir = path.resolve(process.argv[3] || DEFAULT_OUTPUT);

  ensureDir(outDir);

  const dom = await JSDOM.fromFile(htmlPath, {
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true
  });

  await new Promise((resolve) => {
    const done = () => setTimeout(resolve, 60);
    if (dom.window.document.readyState === 'complete') {
      done();
      return;
    }
    dom.window.addEventListener('load', done, { once: true });
  });

  const { document, XMLSerializer } = dom.window;
  const serializer = new XMLSerializer();
  const written = [];

  for (const [id, stem] of Object.entries(FIGURE_NAMES)) {
    const original = document.getElementById(id);
    if (!original) {
      throw new Error(`Missing SVG element: ${id}`);
    }
    const svg = original.cloneNode(true);
    decorateSvg(svg, document);
    const outputPath = path.join(outDir, `${stem}.svg`);
    const svgText = serializer.serializeToString(svg);
    fs.writeFileSync(outputPath, svgText, 'utf8');
    written.push(outputPath);
  }

  const manifestPath = path.join(outDir, 'manifest.json');
  fs.writeFileSync(
    manifestPath,
    JSON.stringify(
      written.map((filePath) => ({
        svg: filePath,
        stem: path.basename(filePath, '.svg')
      })),
      null,
      2
    ) + '\n',
    'utf8'
  );

  for (const filePath of written) {
    console.log(filePath);
  }
  console.log(manifestPath);
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
