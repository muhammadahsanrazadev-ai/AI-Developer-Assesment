import { animate, query, style, transition, trigger } from '@angular/animations';
import { RouterOutlet } from '@angular/router';

export const routeAnimations = trigger('routeAnimations', [
  transition('* <=> *', [
    query(
      ':enter',
      [
        style({ opacity: 0, transform: 'translateY(8px)' }),
        animate('180ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
      ],
      { optional: true },
    ),
  ]),
]);

/** Stable while the user prefers reduced motion, so the transition never runs. */
export function routeAnimationState(outlet: RouterOutlet | undefined): string {
  if (!outlet || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return 'reduced';
  }
  const value = outlet.activatedRouteData['animation'];
  return typeof value === 'string' ? value : 'none';
}
