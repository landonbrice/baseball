import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// Browser-side mock backend. Started from main.jsx only when
// VITE_USE_MOCKS=true, so this module is never loaded in production.
export const worker = setupWorker(...handlers);
