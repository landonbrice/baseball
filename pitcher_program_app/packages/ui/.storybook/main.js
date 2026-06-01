import { mergeConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

/** @type {import('@storybook/react-vite').StorybookConfig} */
export default {
  stories: ['../src/**/*.stories.@(js|jsx)'],
  addons: [],
  framework: { name: '@storybook/react-vite', options: {} },
  // Tailwind v4 processes the tokens + utilities used in stories.
  viteFinal: (config) =>
    mergeConfig(config, {
      plugins: [tailwindcss()],
    }),
};
