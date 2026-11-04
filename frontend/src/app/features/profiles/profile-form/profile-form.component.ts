import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { Component, DestroyRef, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  AbstractControl,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipInput, MatChipInputEvent, MatChipsModule } from '@angular/material/chips';
import { ErrorStateMatcher } from '@angular/material/core';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, RouterLink } from '@angular/router';

import { ApiError } from '../../../core/services/api-error';
import { ProfileService } from '../../../core/services/profile.service';
import { CreateProfileRequest } from '../../../shared/models/profile.model';

/** Same rules as the backend validator in `backend/app/api/profiles.py`. */
const DOMAIN_RE = /^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;
const MAX_COMPETITORS = 10;

export function domainError(raw: string): string | null {
  const value = raw.trim().toLowerCase();
  if (!value) {
    return null;
  }
  if (value.includes('://')) {
    return 'Enter the domain only, without http:// or https:// (e.g. example.com).';
  }
  return DOMAIN_RE.test(value) ? null : 'Enter a valid domain like example.com (no paths or spaces).';
}

export const domainValidator: ValidatorFn = (control: AbstractControl<string>): ValidationErrors | null => {
  const message = domainError(control.value ?? '');
  return message ? { domain: message } : null;
};

const competitorsValidator: ValidatorFn = (control: AbstractControl<string[]>): ValidationErrors | null => {
  const competitors = control.value ?? [];
  if (competitors.length > MAX_COMPETITORS) {
    return { maxCompetitors: `At most ${MAX_COMPETITORS} competitors are allowed.` };
  }
  const ownDomain = (control.parent?.get('domain')?.value ?? '').trim().toLowerCase();
  if (ownDomain && competitors.includes(ownDomain)) {
    return { ownDomain: 'A competitor cannot be the business’s own domain.' };
  }
  return null;
};

@Component({
  selector: 'app-profile-form',
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './profile-form.component.html',
  styleUrl: './profile-form.component.scss',
})
export class ProfileFormComponent {
  private readonly profileService = inject(ProfileService);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly destroyRef = inject(DestroyRef);

  private readonly competitorInput = viewChild.required(MatChipInput);

  protected readonly separatorKeys = [ENTER, COMMA] as const;
  protected readonly maxCompetitors = MAX_COMPETITORS;
  protected readonly submitting = signal(false);
  /** Error for the text currently typed in the competitor input (rejected before it becomes a chip). */
  protected readonly competitorEntryError = signal<string | null>(null);

  protected readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(255)] }),
    domain: new FormControl('', { nonNullable: true, validators: [Validators.required, domainValidator] }),
    industry: new FormControl('', { nonNullable: true, validators: [Validators.required, Validators.maxLength(255)] }),
    description: new FormControl('', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(5000)],
    }),
    competitors: new FormControl<string[]>([], { nonNullable: true, validators: [competitorsValidator] }),
  });

  protected readonly competitorsErrorMatcher: ErrorStateMatcher = {
    isErrorState: (control) =>
      this.competitorEntryError() !== null || !!(control?.invalid && (control.touched || control.dirty)),
  };

  constructor() {
    this.form.controls.domain.valueChanges
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.form.controls.competitors.updateValueAndValidity());
  }

  /** Accepts one domain or a pasted list separated by commas/spaces; invalid entries stay in the input. */
  protected addCompetitor(event: MatChipInputEvent): void {
    const entries = event.value
      .split(/[\s,]+/)
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean);
    const control = this.form.controls.competitors;
    const ownDomain = this.form.controls.domain.value.trim().toLowerCase();
    const accepted = [...control.value];
    const rejected: string[] = [];
    let firstError: string | null = null;

    for (const entry of entries) {
      const message =
        domainError(entry) ??
        (entry === ownDomain ? 'A competitor cannot be the business’s own domain.' : null) ??
        (accepted.includes(entry) ? `${entry} is already in the list.` : null) ??
        (accepted.length >= MAX_COMPETITORS ? `At most ${MAX_COMPETITORS} competitors are allowed.` : null);
      if (message) {
        rejected.push(entry);
        firstError ??= message;
      } else {
        accepted.push(entry);
      }
    }

    if (accepted.length !== control.value.length) {
      control.setValue(accepted);
      control.markAsDirty();
    }
    this.competitorEntryError.set(firstError);
    if (rejected.length) {
      event.chipInput.inputElement.value = rejected.join(', ');
    } else {
      event.chipInput.clear();
    }
  }

  protected removeCompetitor(competitor: string): void {
    const control = this.form.controls.competitors;
    control.setValue(control.value.filter((item) => item !== competitor));
    control.markAsDirty();
  }

  protected clearCompetitorEntryError(): void {
    this.competitorEntryError.set(null);
  }

  protected errorMessage(control: AbstractControl): string | null {
    const errors = control.errors;
    if (!errors) {
      return null;
    }
    if (errors['required']) {
      return 'This field is required.';
    }
    if (errors['maxlength']) {
      return `Must be at most ${errors['maxlength'].requiredLength} characters.`;
    }
    const custom = errors['domain'] ?? errors['maxCompetitors'] ?? errors['ownDomain'] ?? errors['server'];
    return typeof custom === 'string' ? custom : 'This value is invalid.';
  }

  protected submit(): void {
    const chipInput = this.competitorInput();
    if (chipInput.inputElement.value.trim()) {
      this.addCompetitor({ value: chipInput.inputElement.value, input: chipInput.inputElement, chipInput });
    }
    if (this.form.invalid || this.competitorEntryError() !== null || this.submitting()) {
      this.form.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    const payload: CreateProfileRequest = {
      name: raw.name.trim(),
      domain: raw.domain.trim().toLowerCase(),
      industry: raw.industry.trim(),
      description: raw.description.trim(),
      competitors: raw.competitors,
    };

    this.submitting.set(true);
    this.profileService
      .createProfile(payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (profile) => {
          this.snackBar.open(`Profile “${profile.name}” created.`, 'OK');
          void this.router.navigate(['/profiles', profile.profile_uuid]);
        },
        error: (error: ApiError) => {
          this.submitting.set(false);
          this.applyServerErrors(error);
          this.snackBar.open(error.message, 'Dismiss');
        },
      });
  }

  private applyServerErrors(error: ApiError): void {
    for (const [field, message] of Object.entries(error.details)) {
      const name = field.startsWith('competitors') ? 'competitors' : field;
      const control = this.form.get(name);
      if (control) {
        control.setErrors({ ...control.errors, server: message });
        control.markAsTouched();
      }
    }
  }
}
