export type Hook = Record<string, ((...args: unknown[]) => unknown) | undefined>

export function composeHooks(...hooks: Hook[]): Hook {
  const lifecycleNames = new Set(hooks.flatMap(hook => Object.keys(hook)))

  return Object.fromEntries(
    Array.from(lifecycleNames, name => [
      name,
      function (this: unknown, ...args: unknown[]) {
        for (const hook of hooks) {
          hook[name]?.apply(this, args)
        }
      },
    ]),
  )
}
