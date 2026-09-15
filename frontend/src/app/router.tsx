import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router';

import {
  AccountPage,
  LoginPage,
  PasswordResetPage,
  SignupPage,
} from '@/features/auth';
import { ChatIndexPage, ChatServerPage } from '@/features/chat';
import { HomePage } from '@/features/home';
import { IntelClaimPage, IntelEvidencePage, IntelListPage } from '@/features/intel';
import { WorldPage } from '@/features/worlds';

function RootLayout() {
  return (
    <div className="dark min-h-svh bg-background text-foreground">
      <Outlet />
    </div>
  );
}

const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: HomePage,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
});

const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/signup',
  component: SignupPage,
});

const passwordResetRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/password-reset',
  component: PasswordResetPage,
});

const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/account',
  component: AccountPage,
});

const worldRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/w/$worldSlug',
  component: WorldPage,
});

const intelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/w/$worldSlug/intel',
  component: IntelListPage,
});

const intelClaimRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/w/$worldSlug/intel/claims/$claimId',
  component: IntelClaimPage,
});

const intelEvidenceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/w/$worldSlug/intel/evidence/$evidenceId',
  component: IntelEvidencePage,
});

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/chat',
  component: ChatIndexPage,
});

const chatServerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/chat/servers/$serverId',
  component: ChatServerPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  signupRoute,
  passwordResetRoute,
  accountRoute,
  worldRoute,
  intelRoute,
  intelClaimRoute,
  intelEvidenceRoute,
  chatRoute,
  chatServerRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
