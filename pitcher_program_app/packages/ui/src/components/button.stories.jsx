import { Button } from './button';

export default {
  title: 'Primitives/Button',
  component: Button,
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'secondary', 'outline', 'ghost', 'destructive', 'link'],
    },
    size: { control: 'select', options: ['sm', 'md', 'lg', 'icon'] },
    children: { control: 'text' },
  },
  args: { children: 'Generate plan', variant: 'default', size: 'md' },
};

export const Default = {};

export const Secondary = { args: { variant: 'secondary', children: 'Save draft' } };

export const Outline = { args: { variant: 'outline', children: 'View program' } };

export const Ghost = { args: { variant: 'ghost', children: 'Skip' } };

export const Destructive = { args: { variant: 'destructive', children: 'Archive program' } };

export const Link = { args: { variant: 'link', children: 'Why this plan?' } };

export const AllVariants = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button>Default</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="destructive">Destructive</Button>
      <Button variant="link">Link</Button>
    </div>
  ),
};

export const Sizes = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button size="sm">Small</Button>
      <Button size="md">Medium</Button>
      <Button size="lg">Large</Button>
    </div>
  ),
};
