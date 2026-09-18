import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./session-picker/session-picker.component').then((m) => m.SessionPickerComponent),
  },
  {
    path: 'replay',
    loadComponent: () =>
      import('./replay-view/replay-view.component').then((m) => m.ReplayViewComponent),
  },
];
