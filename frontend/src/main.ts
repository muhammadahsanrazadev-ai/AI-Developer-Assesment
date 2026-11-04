import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';
import { applyStoredTheme } from './app/core/services/theme.service';

applyStoredTheme();

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
