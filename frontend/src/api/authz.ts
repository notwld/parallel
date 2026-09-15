/** D018: UI gates from server allowlists only. Never invent privileges client-side. */

export function can(action: string, allowedActions: readonly string[] | undefined | null): boolean {
  return Boolean(allowedActions?.includes(action));
}

export function canAny(
  actions: readonly string[],
  allowedActions: readonly string[] | undefined | null,
): boolean {
  return actions.some((action) => can(action, allowedActions));
}
