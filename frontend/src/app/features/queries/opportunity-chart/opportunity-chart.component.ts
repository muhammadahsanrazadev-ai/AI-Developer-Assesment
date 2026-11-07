import { Component, DestroyRef, OnInit, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatSnackBar } from '@angular/material/snack-bar';
import { BarController, BarElement, CategoryScale, ChartConfiguration, LinearScale, Tooltip } from 'chart.js';
import { BaseChartDirective, provideCharts } from 'ng2-charts';
import { filter, skip } from 'rxjs';

import { ApiError } from '../../../core/services/api-error';
import { PipelineService } from '../../../core/services/pipeline.service';
import { QueryService } from '../../../core/services/query.service';
import { ThemeService } from '../../../core/services/theme.service';
import { SkeletonComponent } from '../../../shared/components/skeleton/skeleton.component';
import { DiscoveredQuery } from '../../../shared/models/query.model';

/** The API's maximum page size; one run produces at most 20 queries. */
const CHART_PAGE_SIZE = 100;
const LABEL_MAX_LENGTH = 30;
/** Room for a 30-character label drawn at 40 degrees, so neighbours do not cover each other. */
const PIXELS_PER_BAR = 160;

export const BAR_COLOURS = {
  visible: '#1e88e5',
  notVisible: '#fb8c00',
  unknown: '#9e9e9e',
} as const;

export function truncateLabel(text: string, maxLength = LABEL_MAX_LENGTH): string {
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

function barColour(query: DiscoveredQuery): string {
  if (query.domain_visible === null) {
    return BAR_COLOURS.unknown;
  }
  return query.domain_visible ? BAR_COLOURS.visible : BAR_COLOURS.notVisible;
}

@Component({
  selector: 'app-opportunity-chart',
  imports: [BaseChartDirective, MatButtonModule, MatCardModule, MatIconModule, SkeletonComponent],
  providers: [provideCharts({ registerables: [BarController, BarElement, CategoryScale, LinearScale, Tooltip] })],
  templateUrl: './opportunity-chart.component.html',
  styleUrl: './opportunity-chart.component.scss',
})
export class OpportunityChartComponent implements OnInit {
  readonly profileUuid = input.required<string>();

  private readonly queryService = inject(QueryService);
  private readonly pipelineService = inject(PipelineService);
  private readonly snackBar = inject(MatSnackBar);
  private readonly theme = inject(ThemeService);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly skeletonBars = [80, 150, 110, 190, 60, 140, 95, 170];

  protected readonly colours = BAR_COLOURS;
  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly hasRun = signal(false);
  protected readonly queries = signal<DiscoveredQuery[]>([]);
  protected readonly unscoredCount = signal(0);
  protected readonly hasUnknown = computed(() => this.queries().some((query) => query.domain_visible === null));
  protected readonly chartMinWidth = computed(() => `${this.queries().length * PIXELS_PER_BAR}px`);

  protected readonly chartData = computed<ChartConfiguration<'bar'>['data']>(() => {
    const queries = this.queries();
    return {
      labels: queries.map((query) => truncateLabel(query.query_text)),
      datasets: [
        {
          label: 'Opportunity score',
          data: queries.map((query) => query.opportunity_score ?? 0),
          backgroundColor: queries.map(barColour),
          borderRadius: 4,
          maxBarThickness: 48,
        },
      ],
    };
  });

  protected readonly chartOptions = computed<ChartConfiguration<'bar'>['options']>(() => {
    const ink = this.theme.dark() ? '#e8eaed' : '#3c4043';
    const grid = this.theme.dark() ? 'rgba(255,255,255,0.16)' : 'rgba(0,0,0,0.08)';
    return {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        title: { display: true, text: 'Query', color: ink },
        ticks: {
          autoSkip: false,
          maxRotation: 40,
          minRotation: 40,
          color: ink,
          padding: 8,
          font: { size: 12 },
        },
        grid: { color: grid },
      },
      y: {
        min: 0,
        max: 1,
        title: { display: true, text: 'Opportunity score', color: ink },
        ticks: { stepSize: 0.1, color: ink },
        grid: { color: grid },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => this.queries()[items[0]?.dataIndex ?? 0]?.query_text ?? '',
          label: (item) => {
            const query = this.queries()[item.dataIndex];
            const visibility =
              query?.domain_visible === null ? 'unknown' : query?.domain_visible ? 'visible' : 'not visible';
            return `Score ${Number(item.raw).toFixed(2)} · ${visibility}`;
          },
        },
      },
    },
  };
  });

  constructor() {
    toObservable(this.pipelineService.lastFinishedRun)
      .pipe(
        skip(1),
        filter((run) => run?.profile_uuid === this.profileUuid()),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.load());
  }

  ngOnInit(): void {
    this.load();
  }

  protected load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.queryService
      .getQueries(this.profileUuid(), { page: 1, per_page: CHART_PAGE_SIZE })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (page) => {
          this.hasRun.set(page.run_uuid !== null);
          const scored = page.items.filter((query) => query.opportunity_score !== null);
          this.unscoredCount.set(page.items.length - scored.length);
          this.queries.set(scored);
          this.loading.set(false);
        },
        error: (error: ApiError) => {
          this.error.set(error.message);
          this.loading.set(false);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }
}
