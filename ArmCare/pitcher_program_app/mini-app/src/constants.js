/**
 * Shared color palette for flag levels and arm feel visualization.
 */

export const FLAG_COLORS = {
  green: {
    bg: 'bg-flag-green/15',
    text: 'text-flag-green',
    stroke: '#1D9E75',
  },
  yellow: {
    bg: 'bg-flag-yellow/15',
    text: 'text-flag-yellow',
    stroke: '#BA7517',
  },
  red: {
    bg: 'bg-flag-red/15',
    text: 'text-flag-red',
    stroke: '#A32D2D',
  },
};

export function getArmFeelLevel(feel) {
  if (feel >= 4) return 'green';
  if (feel === 3) return 'yellow';
  return 'red';
}
