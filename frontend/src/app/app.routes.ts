import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'Dashboard · AI Visibility Intelligence',
    data: { animation: 'dashboard' },
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
  },
  {
    path: 'profiles/new',
    title: 'New Business Profile · AI Visibility Intelligence',
    data: { animation: 'profile-form' },
    loadComponent: () =>
      import('./features/profiles/profile-form/profile-form.component').then(
        (m) => m.ProfileFormComponent,
      ),
  },
  {
    path: 'profiles/:profileUuid',
    data: { animation: 'profile' },
    loadComponent: () =>
      import('./features/profiles/profile-detail/profile-detail.component').then(
        (m) => m.ProfileDetailComponent,
      ),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'queries' },
      {
        path: 'queries',
        data: { animation: 'queries' },
        loadComponent: () =>
          import('./features/queries/queries-table/queries-table.component').then(
            (m) => m.QueriesTableComponent,
          ),
      },
      {
        path: 'chart',
        data: { animation: 'chart' },
        loadComponent: () =>
          import('./features/queries/opportunity-chart/opportunity-chart.component').then(
            (m) => m.OpportunityChartComponent,
          ),
      },
      {
        path: 'recommendations',
        data: { animation: 'recommendations' },
        loadComponent: () =>
          import(
            './features/recommendations/recommendations-list/recommendations-list.component'
          ).then((m) => m.RecommendationsListComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
