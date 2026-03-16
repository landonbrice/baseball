/**
 * Shared color palette for flag levels and arm feel visualization.
 */

export const FLAG_COLORS = {
  green: {
    bg: 'bg-[#064e3b]',
    text: 'text-flag-green',
    stroke: '#4ade80',
  },
  yellow: {
    bg: 'bg-[#713f12]',
    text: 'text-flag-yellow',
    stroke: '#facc15',
  },
  red: {
    bg: 'bg-[#7f1d1d]',
    text: 'text-flag-red',
    stroke: '#ef4444',
  },
};

export function getArmFeelLevel(feel) {
  if (feel >= 4) return 'green';
  if (feel === 3) return 'yellow';
  return 'red';
}
