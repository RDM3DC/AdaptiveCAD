import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

export default defineConfig({
  site: 'https://rdm3dc.github.io',
  base: '/AdaptiveCAD',
  integrations: [mdx()],
  markdown: {
    shikiConfig: {
      theme: 'github-dark'
    }
  },
  // GitHub Pages specific configuration
  output: 'static',
  build: {
    assets: '_astro'
  }
});