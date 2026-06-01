import { FlagPill } from './flag-pill';

export default {
  title: 'Primitives/FlagPill',
  component: FlagPill,
  argTypes: {
    level: { control: 'select', options: ['green', 'yellow', 'red'] },
    children: { control: 'text' },
  },
  args: { level: 'green' },
};

export const Green = { args: { level: 'green' } };
export const Yellow = { args: { level: 'yellow' } };
export const Red = { args: { level: 'red' } };

export const WithSuffix = {
  args: { level: 'yellow', children: 'Yellow · tissue 2.3' },
};

export const AllLevels = {
  render: () => (
    <div className="flex items-center gap-3">
      <FlagPill level="green" />
      <FlagPill level="yellow" />
      <FlagPill level="red" />
    </div>
  ),
};
