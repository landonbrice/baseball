import './preview.css';

/**
 * Brand-switcher toolbar — flips <html data-brand="..."> live so every story
 * re-skins between UChicago (canonical) and Cue (placeholder) with one click.
 * This is the load-bearing demo of the dual-brand token system.
 */
export const globalTypes = {
  brand: {
    description: 'Active brand theme',
    defaultValue: 'uchicago',
    toolbar: {
      title: 'Brand',
      icon: 'paintbrush',
      items: [
        { value: 'uchicago', title: 'UChicago' },
        { value: 'cue', title: 'Cue (placeholder)' },
      ],
      dynamicTitle: true,
    },
  },
};

const withBrand = (Story, context) => {
  const brand = context.globals.brand || 'uchicago';
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-brand', brand);
  }
  return <Story />;
};

/** @type {import('@storybook/react-vite').Preview} */
const preview = {
  decorators: [withBrand],
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    layout: 'centered',
  },
};

export default preview;
