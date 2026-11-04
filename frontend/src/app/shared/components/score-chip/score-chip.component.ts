import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type ScoreBand = 'high' | 'medium' | 'low';

/** Spec thresholds: green >= 0.7, yellow 0.4-0.69, red < 0.4. */
export function scoreBand(score: number): ScoreBand {
  if (score >= 0.7) {
    return 'high';
  }
  return score >= 0.4 ? 'medium' : 'low';
}

@Component({
  selector: 'app-score-chip',
  imports: [DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (score() !== null) {
      <span class="score-chip" [class]="'score-chip--' + band()">
        {{ score() | number: '1.2-2' }}
      </span>
    } @else {
      <span class="score-chip score-chip--none">n/a</span>
    }
  `,
  styleUrl: './score-chip.component.scss',
})
export class ScoreChipComponent {
  readonly score = input<number | null>(null);
  protected readonly band = computed(() => {
    const value = this.score();
    return value === null ? null : scoreBand(value);
  });
}
